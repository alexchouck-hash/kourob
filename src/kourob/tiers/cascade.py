"""The cascade: try the cheapest tier that meets the quality bar; log every attempt.

Brief reference: section 3.1 step 4.

Every attempt is logged, including the ones that missed, because a tier that is tried and
declines still costs money and is still evidence. A node that only charges for the tier that
succeeded is hiding its own cascade inefficiency from itself, and that is the number the
evolve loop needs most (KNP-3 section 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kourob.manifest import Manifest
from kourob.tiers.base import Request, TierHandler, TierResult
from kourob.types import Tier

__milestone__ = "M1"

#: Cheapest first. The cascade never reorders this.
TIER_ORDER = (Tier.T0, Tier.T1, Tier.T2, Tier.T3, Tier.T4)


@dataclass
class Attempt:
    tier: Tier
    answered: bool
    confidence: float
    cost_credits: float
    cleared_bar: bool
    detail: str = ""


@dataclass
class CascadeResult:
    result: TierResult | None
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        """Everything the cascade spent, not just the tier that answered."""
        return sum(a.cost_credits for a in self.attempts)

    @property
    def answered(self) -> bool:
        return self.result is not None and self.result.answered


class Cascade:
    """Ordered tiers plus the manifest's confidence bars."""

    def __init__(self, manifest: Manifest, handlers: dict[Tier, TierHandler]) -> None:
        self.manifest = manifest
        self.handlers = handlers

    def run(self, request: Request) -> CascadeResult:
        out = CascadeResult(result=None)
        for tier in TIER_ORDER:
            handler = self.handlers.get(tier)
            if handler is None or not self.manifest.tier_enabled(tier) or not handler.available():
                continue
            result = handler.attempt(request)
            bar = self.manifest.confidence_bar(tier)
            cleared = result.answered and result.confidence >= bar
            out.attempts.append(
                Attempt(
                    tier=tier,
                    answered=result.answered,
                    confidence=result.confidence,
                    cost_credits=result.cost_credits,
                    cleared_bar=cleared,
                    detail=result.detail,
                )
            )
            if cleared:
                out.result = result
                return out
        return out


__all__ = ["TIER_ORDER", "Attempt", "Cascade", "CascadeResult"]
