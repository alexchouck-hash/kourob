"""The price function and quotes: what a caller is charged, and what it is promised.

Brief reference: section 5.1. KNP-3 sections 1 to 3. ADR-0004 (owed).

    price = base_cost(tier_used) * (1 + demand_factor) * quality_multiplier

Cost is *measured* by the runner; price is *computed* here. Demand rations the node and
funds its split (brief section 5.1). Quality is earned from settled outcomes, never set: a
node that answers confidently and wrongly gets cheaper, and one nobody checks drifts to
`q_min` (KNP-3 section 3).

A quote carries a **ceiling** - the price if the cascade falls all the way through - and a
node never charges above the ceiling it quoted. The cascade's uncertainty is the node's
risk, not the caller's.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from kourob import events as ev
from kourob.types import ScopeResult, Tier

__milestone__ = "M4"

#: Fallback base costs when no manifest is in play (the eval calls `price_for` bare).
DEFAULT_BASE_COST: dict[Tier, float] = {
    Tier.T0: 0.0001,
    Tier.T1: 0.0005,
    Tier.T2: 0.002,
    Tier.T3: 0.02,
    Tier.T4: 1.0,
}

QUOTE_TTL = timedelta(minutes=5)
Q_MIN, Q_MAX = 0.5, 1.5


def demand_factor(requests_in_window: int, capacity_window: int, max_surge: float) -> float:
    """Brief section 5.1: zero below capacity, rising with load, capped at `max_surge`."""
    if capacity_window <= 0:
        return 0.0
    return max(0.0, min(max_surge, requests_in_window / capacity_window - 1.0))


def price_for(
    tier: Tier,
    *,
    requests_in_window: int,
    capacity_window: int,
    max_surge: float,
    base_cost: dict[Tier, float] | None = None,
    quality_multiplier: float = 1.0,
) -> float:
    """The price of one answer at `tier`, under this load, at this earned quality."""
    base = (base_cost or DEFAULT_BASE_COST).get(tier, 0.0)
    surge = 1.0 + demand_factor(requests_in_window, capacity_window, max_surge)
    return base * surge * max(Q_MIN, min(Q_MAX, quality_multiplier))


class Quote(BaseModel):
    """What a caller is promised before committing (KNP-3 section 2)."""

    quote_id: str
    scope_result: ScopeResult
    expected_tier: Tier | None
    price_credits: float
    price_ceiling_credits: float
    demand_factor: float
    quality_multiplier: float
    upstream: list[str] = Field(default_factory=list)
    expires: datetime
    balance_credits: float
    free_allowance_remaining: int

    def affordable(self) -> bool:
        """Free requests remain, or the balance covers the ceiling — never just the price."""
        return (
            self.free_allowance_remaining > 0 or self.balance_credits >= self.price_ceiling_credits
        )


class Pricer:
    """Prices for one node, from its manifest, its request log and its settled outcomes."""

    def __init__(self, node: Any, *, now: datetime | None = None) -> None:
        self.node = node
        self.manifest = node.manifest
        self.now = now or ev.now()
        self._quality: float | None = None
        self._volume: int | None = None

    # ----------------------------------------------------------------- inputs

    def window(self) -> timedelta:
        from kourob.ledger.outcomes import parse_window

        return parse_window(self.manifest.pricing.window) or timedelta(hours=1)

    def requests_in_window(self, caller: str | None = None) -> int:
        """Requests this node served in the pricing window - all callers, or one."""
        if self._volume is not None and caller is None:
            return self._volume
        store = self.node.store
        if store.stats("requests")["rows"] == 0:
            return 0
        since = (self.now - self.window()).isoformat()
        sql = "SELECT count(*) AS n FROM requests WHERE ts >= $since"
        params: dict[str, Any] = {"since": since}
        if caller is not None:
            sql += " AND caller = $caller"
            params["caller"] = caller
        count = int(store.query(sql, params).to_pylist()[0]["n"] or 0)
        if caller is None:
            self._volume = count
        return count

    def quality(self) -> float:
        if self._quality is None:
            from kourob.ledger.outcomes import settlement_status

            status = settlement_status(self.node.ledger, self.node.contracts, now=self.now)
            self._quality = status.quality_multiplier(Q_MIN, Q_MAX)
        return self._quality

    def demand(self) -> float:
        pricing = self.manifest.pricing
        return demand_factor(self.requests_in_window(), pricing.capacity_window, pricing.max_surge)

    # ------------------------------------------------------------------ prices

    def price(self, tier: Tier | None) -> float:
        if tier is None:
            return 0.0
        pricing = self.manifest.pricing
        return price_for(
            tier,
            requests_in_window=self.requests_in_window(),
            capacity_window=pricing.capacity_window,
            max_surge=pricing.max_surge,
            base_cost=pricing.base_cost,
            quality_multiplier=self.quality(),
        )

    def ceiling(self) -> float:
        """The price at the dearest enabled tier: what a cascade that falls through costs."""
        enabled = [t for t in Tier if self.manifest.tier_enabled(t)]
        return max((self.price(t) for t in enabled), default=0.0)

    def free_remaining(self, caller: str) -> int:
        return max(0, self.manifest.pricing.free_allowance - self.requests_in_window(caller))

    # ------------------------------------------------------------------ quotes

    def quote(self, question: str, caller: str, *, hops: list[str] | None = None) -> Quote:
        """Scope-check without running a tier, predict the tier, and promise a ceiling."""
        from kourob import scope as scope_mod
        from kourob.ledger.accounts import Accounts
        from kourob.routes import RouteTable
        from kourob.tiers.t0_rules import load_rules

        routes = RouteTable(self.node.store, self.manifest.prune)
        decision = scope_mod.check(
            self.manifest, routes, question, own_did=self.node.did, hops=list(hops or [])
        )
        expected: Tier | None
        if decision.result is not ScopeResult.IN_SCOPE:
            expected = None
        elif any(rule.bind(question) for rule in load_rules(self.node.dir)):
            expected = Tier.T0
        else:
            enabled = [t for t in Tier if self.manifest.tier_enabled(t) and t is not Tier.T0]
            expected = enabled[-1] if enabled else None

        return Quote(
            quote_id=ev.new_id("qt_"),
            scope_result=decision.result,
            expected_tier=expected,
            price_credits=self.price(expected),
            price_ceiling_credits=self.ceiling() if expected is not None else 0.0,
            demand_factor=self.demand(),
            quality_multiplier=self.quality(),
            expires=self.now + QUOTE_TTL,
            balance_credits=Accounts(self.node.store).balance(caller),
            free_allowance_remaining=self.free_remaining(caller),
        )


__all__ = ["DEFAULT_BASE_COST", "Pricer", "Quote", "demand_factor", "price_for"]
