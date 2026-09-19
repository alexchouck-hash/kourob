"""Outcomes: the record that says whether an answer was any good.

Brief reference: KNP-2 section 6, ADR-0007.

A receipt records what a node did. It says nothing about whether the answer held up.
Without that, the request log is a pile of unlabelled examples and the evolve loop can make
a node cheaper but not better — and cheaper-but-wrong is the failure mode that kills this
design.

An outcome is appended to the same hash chain as receipts and never edits the receipt it
judges. The wrong answer stays in the chain with a correction pointing at what was true.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

__milestone__ = "M4"


class Verdict(StrEnum):
    """How an answer turned out."""

    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    UNRESOLVED = "unresolved"  # window expired with nothing said


class OutcomeSource(StrEnum):
    """Who says so. Ordered by how much the node should believe them."""

    CALLER = "caller"  # self-reported, may be strategic
    DOWNSTREAM = "downstream"  # a node that used this answer; has skin in it
    HUMAN = "human"  # T4 review or a correction pushed through the gate
    REALITY = "reality"  # a later event settles it; nobody's opinion


#: Default weights when an outcome is used as a training label or feeds the quality
#: multiplier. Policy, not protocol (ADR-0007, Consequences) — expect to tune these.
SOURCE_WEIGHT = {
    OutcomeSource.CALLER: 0.25,
    OutcomeSource.DOWNSTREAM: 0.5,
    OutcomeSource.HUMAN: 1.0,
    OutcomeSource.REALITY: 1.0,
}

#: Fields covered by `sig`, in order. Changing this is a breaking ledger change.
SIGNED_FIELDS = (
    "id",
    "node",
    "about",
    "verdict",
    "source",
    "evidence",
    "latency_s",
    "ts",
    "prev",
)


class Outcome(BaseModel):
    """A signed judgement of one receipt, appended to the same chain."""

    id: str = Field(description="ULID, prefixed outc_")
    node: str = Field(description="did:key of the node whose ledger this is")
    about: str = Field(description="the receipt id being judged")
    verdict: Verdict
    source: OutcomeSource
    evidence: list[str] = Field(
        default_factory=list,
        description="event ids that settle it. Required for verdict=corrected: the "
        "correction must point at what was true, not merely say the answer was wrong.",
    )
    by: str | None = Field(default=None, description="did:key or user:<id> who reported it")
    note: str | None = None
    latency_s: float | None = Field(
        default=None, description="seconds between the answer and the outcome being known"
    )
    ts: datetime
    prev: str = Field(description="sha256: of the previous ledger record on this node")
    sig: str = Field(description="ed25519 signature over SIGNED_FIELDS")

    model_config = {"frozen": True}

    @property
    def weight(self) -> float:
        """How much this outcome should count. See SOURCE_WEIGHT."""
        return SOURCE_WEIGHT[self.source]

    @property
    def is_settled(self) -> bool:
        """Unresolved is information, not a settlement (KNP-3 section 3)."""
        return self.verdict is not Verdict.UNRESOLVED


__all__ = ["SIGNED_FIELDS", "SOURCE_WEIGHT", "Outcome", "OutcomeSource", "Verdict"]
