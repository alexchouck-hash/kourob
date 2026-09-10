"""The Tier interface: attempt(request) returns a TierResult the cascade can compare.

Brief reference: section 3.1 step 4. Determinism classes: KNP-0 section 2.

Every tier answers the same question and reports how sure it is, in the same units, so the
cascade can compare a rule against a frontier model without knowing what either is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from kourob.types import TIER_DETERMINISM, Determinism, Tier

__milestone__ = "M1"


@dataclass
class Request:
    """One question, plus what the node needs to route and meter it."""

    question: str
    caller: str = "user:local"
    hops: list[str] = field(default_factory=list)
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class TierResult:
    """What one tier produced, and how much the node should believe it."""

    tier: Tier
    answered: bool
    confidence: float = 0.0
    data: Any = None
    rendered: str = ""
    citations: list[str] = field(default_factory=list)
    model_version: str = ""
    cost_credits: float = 0.0
    detail: str = ""
    settle_key: str | None = None
    """What this answer is *about*, hashed, when the tier can say (KNP-2 section 6.2).

    Only tiers with a structured subject can produce one. A T3 answer to a free-text
    question has no subject the node can name, so it stays None and the receipt is simply
    never settled by a later event. That is a real limit, not an oversight."""

    @property
    def determinism(self) -> Determinism:
        return TIER_DETERMINISM[self.tier]

    @classmethod
    def miss(cls, tier: Tier, detail: str = "") -> TierResult:
        """A tier that declined. Declining is normal and is not an error."""
        return cls(tier=tier, answered=False, detail=detail)


class TierHandler(ABC):
    """One execution path. Cheap ones are tried first."""

    tier: Tier

    @abstractmethod
    def attempt(self, request: Request) -> TierResult:
        """Answer, or decline. Never raise for "I cannot answer this" — that is a miss."""

    def available(self) -> bool:
        """Whether this tier can run at all: weights present, key configured, gold exists."""
        return True


__all__ = ["Request", "TierHandler", "TierResult"]
