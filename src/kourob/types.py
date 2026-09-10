"""The shapes every port speaks.

Brief reference: sections 3.1 step 5 and 13.5.

Rule from AGENTS.md section 4: every port handler returns
``{data, rendered, citations, receipt_id}``. No exceptions, including errors and
referrals. `Answer` is that contract, expressed once so no port can drift from it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

__milestone__ = "M0"


class ScopeResult(StrEnum):
    """Outcome of the scope check (brief section 3.1 step 2)."""

    IN_SCOPE = "in_scope"
    REFERRAL = "referral"
    REJECT = "reject"
    BRIDGE = "bridge"


class Tier(StrEnum):
    """Execution tiers, ordered by cost. The node tries the cheapest that meets the bar."""

    T0 = "T0"  # rules, SQL over silver, exact-match cache
    T1 = "T1"  # distilled student model
    T2 = "T2"  # mid model
    T3 = "T3"  # frontier model
    T4 = "T4"  # human review queue


class Determinism(StrEnum):
    """What a third party can do with the answer (KNP-0 section 2).

    This is a *trust* ordering, and it does not map one-to-one onto the cost ordering in
    `Tier`: a cheap T0 answer is more verifiable than an expensive T3 one. As a node
    promotes work down the tiers it gets cheaper and more checkable along the same axis,
    which is the point.
    """

    DERIVED = "derived"  # T0: re-runnable by anyone holding the events
    ATTESTED = "attested"  # T1-T3: proves the node said it, not that it follows
    ADJUDICATED = "adjudicated"  # T4: attested, plus a named human accepted it


#: Which determinism class each tier produces. T4 is adjudicated; everything between
#: T0 and T4 is attested.
TIER_DETERMINISM = {
    Tier.T0: Determinism.DERIVED,
    Tier.T1: Determinism.ATTESTED,
    Tier.T2: Determinism.ATTESTED,
    Tier.T3: Determinism.ATTESTED,
    Tier.T4: Determinism.ADJUDICATED,
}


class RefusalReason(StrEnum):
    """Why a request was rejected (KNP-1 section 6).

    A node must not collapse these into a single "no": the difference between "not mine"
    and "mine but I cannot right now" is the difference between the caller re-routing and
    the caller retrying, and getting it wrong wastes the network money.
    """

    OUT_OF_SCOPE = "out_of_scope"
    LOOP = "loop"
    INSUFFICIENT_CREDIT = "insufficient_credit"
    HOPS_EXHAUSTED = "hops_exhausted"
    POLICY = "policy"
    UNAVAILABLE = "unavailable"


class RouteHint(BaseModel):
    """What a bridging node hands back so the caller does not need the bridge again.

    Brief section 3.2.
    """

    node: str = Field(description="did:key of the node that can answer directly")
    scope: str = Field(description="the scope pattern this node claims")
    cost_credits: float | None = Field(default=None, description="observed price")
    latency_ms: float | None = Field(default=None, description="observed latency")


class Answer(BaseModel):
    """The single return shape of every port handler.

    ``citations`` are event ids. An answer with no citations is only valid when
    ``scope_result`` is REFERRAL or REJECT, and lint will flag it anywhere else.
    """

    data: Any = Field(description="structured result, typed by the schema it came from")
    rendered: str = Field(description="markdown view of the same result")
    citations: list[str] = Field(default_factory=list, description="event ids")
    receipt_id: str = Field(description="the receipt this answer was recorded under")

    scope_result: ScopeResult = ScopeResult.IN_SCOPE
    tier_used: Tier | None = None
    determinism: Determinism | None = None
    reason: RefusalReason | None = None
    route_hints: list[RouteHint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="A2A metadata, keyed by extension URI per ADR-0006. Use protocols.key().",
    )

    def is_grounded(self) -> bool:
        """An answer must cite events unless it refused.

        KNP-0 I1: empty citations are legal only for a referral or a reject. Anywhere else
        an empty list means the node produced a claim it cannot source.
        """
        if self.scope_result in (ScopeResult.REFERRAL, ScopeResult.REJECT):
            return True
        return bool(self.citations)


__all__ = [
    "TIER_DETERMINISM",
    "Answer",
    "Determinism",
    "RefusalReason",
    "RouteHint",
    "ScopeResult",
    "Tier",
]
