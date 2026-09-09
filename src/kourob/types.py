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
    route_hints: list[RouteHint] = Field(default_factory=list)


__all__ = ["Answer", "RouteHint", "ScopeResult", "Tier"]
