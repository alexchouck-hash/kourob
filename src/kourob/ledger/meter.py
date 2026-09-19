"""`kourob meter report`: revenue, cost, margin, and who is paying for it.

Brief reference: section 4.4. KNP-3 section 1, KNP-7 section 3.

Cost is measured (the runner), price is computed (the pricer), and this is where the two
meet as a number the operator can read. `surplus = revenue - serving_cost` is the quantity
KNP-7 makes a node's autonomy depend on: a node nobody calls earns nothing and cannot fund
its own improvement, which is the selection pressure the design needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from kourob import events as ev

__milestone__ = "M4"


@dataclass
class MeterReport:
    node: str
    period: str
    since: datetime
    requests: int = 0
    answered: int = 0
    revenue: float = 0.0
    cost: float = 0.0
    model_spend: float = 0.0
    by_tier: dict[str, dict[str, float]] = field(default_factory=dict)
    top_callers: list[tuple[str, int, float]] = field(default_factory=list)
    balances: dict[str, float] = field(default_factory=dict)

    @property
    def margin(self) -> float:
        return self.revenue - self.cost

    @property
    def state(self) -> str:
        """KNP-7 section 3.1: growing, stable, or failing. Nominal until credits are real."""
        if self.margin > 0:
            return "growing"
        if self.margin == 0:
            return "stable"
        return "failing"

    def render(self) -> str:
        lines = [
            f"meter for {self.node[:24]}...  period {self.period} (since {self.since:%Y-%m-%d})",
            f"  requests   {self.requests}  ({self.answered} answered)",
            f"  revenue    {self.revenue:.6f}",
            f"  cost       {self.cost:.6f}  (of which model calls {self.model_spend:.6f})",
            f"  margin     {self.margin:+.6f}  -> {self.state}",
        ]
        if self.by_tier:
            lines.append("  by tier:")
            for tier, row in sorted(self.by_tier.items()):
                lines.append(
                    f"    {tier:<3} {int(row['n']):>5}  revenue {row['revenue']:.6f}  "
                    f"cost {row['cost']:.6f}"
                )
        if self.top_callers:
            lines.append("  top callers:")
            for caller, n, paid in self.top_callers[:5]:
                lines.append(f"    {caller:<28} {n:>5}  paid {paid:.6f}")
        if self.balances:
            lines.append("  balances:")
            for caller, balance in sorted(self.balances.items()):
                lines.append(f"    {caller:<28} {balance:+.6f}")
        return "\n".join(lines)


def _since(period: str, now: datetime) -> datetime:
    from kourob.ledger.outcomes import parse_window

    if period == "all":
        return datetime.min.replace(tzinfo=now.tzinfo)
    try:
        return now - (parse_window(period) or timedelta(days=30))
    except ValueError:
        return datetime.fromisoformat(period).replace(tzinfo=now.tzinfo)


def report(
    node_dir: Path | str, period: str = "30d", *, now: datetime | None = None
) -> MeterReport:
    from kourob.ledger.accounts import Accounts
    from kourob.node import open_node

    node = open_node(node_dir)
    stamp = now or ev.now()
    since = _since(period, stamp)
    out = MeterReport(node=node.did, period=period, since=since)

    store = node.store
    if store.stats("requests")["rows"]:
        rows = store.query(
            "SELECT caller, tier_used, scope_result, cost_credits, price_credits "
            "FROM requests WHERE ts >= $since",
            {"since": since.isoformat()},
        ).to_pylist()
        callers: dict[str, list[float]] = {}
        for row in rows:
            out.requests += 1
            price = float(row.get("price_credits") or 0.0)
            cost = float(row.get("cost_credits") or 0.0)
            out.revenue += price
            out.cost += cost
            tier = str(row.get("tier_used") or "-")
            if row.get("scope_result") == "in_scope":
                out.answered += 1
            bucket = out.by_tier.setdefault(tier, {"n": 0, "revenue": 0.0, "cost": 0.0})
            bucket["n"] += 1
            bucket["revenue"] += price
            bucket["cost"] += cost
            caller = str(row.get("caller") or "?")
            entry = callers.setdefault(caller, [0, 0.0])
            entry[0] += 1
            entry[1] += price
        out.top_callers = sorted(
            ((c, int(n), paid) for c, (n, paid) in callers.items()), key=lambda t: (-t[2], -t[1])
        )

    if store.stats("calls")["rows"]:
        spend = store.query(
            "SELECT sum(cost_credits) AS s FROM calls WHERE ts >= $since",
            {"since": since.isoformat()},
        ).to_pylist()
        out.model_spend = float(spend[0]["s"] or 0.0)

    out.balances = Accounts(store).statement()
    return out


__all__ = ["MeterReport", "report"]
