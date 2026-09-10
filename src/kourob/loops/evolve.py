"""evolve: make this node cheaper at its own job without making it worse.

Brief reference: sections 5.2 and 6.1. Specified in docs/protocols/knp-5-evolution.md.
Decided in ADR-0005 (owed), ADR-0007, ADR-0008.

The loop does not optimise the node. It optimises **clusters of demand** discovered from
the request log, and it emits proposals, never silent changes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from kourob.types import Tier

__milestone__ = "M4"


class ProposalKind(StrEnum):
    """What the loop can propose. Each becomes at most one PR."""

    PROMOTE = "promote"  # move a cluster to a cheaper tier (KNP-5 section 3)
    DEMOTE = "demote"  # evidence stopped holding (KNP-5 section 5)
    SHED = "shed"  # drop scope nobody pulls (KNP-5 section 6)
    SPLIT = "split"  # spawn a child for a distinguishable cluster (KNP-5 section 7)
    MERGE = "merge"  # two under-utilised siblings rejoin
    RULE_FROM_QUARANTINE = "rule_from_quarantine"  # repeated gate rejections became a pattern
    SCOPE_DRIFT = "scope_drift"  # declared and served scope diverged (KNP-1 section 7)


class ClusterStats(BaseModel):
    """One cluster of demand, per window.

    Clustering is over discrete features — scope label, schemas touched, tools called,
    answer shape — not embeddings. Requests are short and already typed; an embedding would
    add a dependency, a failure mode, and no accuracy.
    """

    key: str
    volume: int
    tier_mix: dict[Tier, float] = Field(default_factory=dict)
    cost_per_settled: float | None = Field(
        default=None, description="None when settle_rate is 0: the objective is undefined"
    )
    settle_rate: float = Field(ge=0.0, le=1.0)
    accept_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    event_fanout: float = 0.0
    answer_entropy: float = Field(
        default=1.0,
        description="distinct answers per distinct (question, event-set). 1.0 means the "
        "cluster is a function, and functions belong in T0.",
    )
    schemas: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    @property
    def is_function(self) -> bool:
        """A cluster whose answer has always been determined by its inputs."""
        return self.answer_entropy == 1.0

    @property
    def can_promote(self) -> bool:
        """Unverifiable work does not get to be cheap (ADR-0007, Consequences)."""
        return self.settle_rate > 0.0


class Proposal(BaseModel):
    """A change the loop wants a human to accept. Never applied automatically."""

    kind: ProposalKind
    cluster: str | None = None
    clusters: list[str] = Field(default_factory=list)
    from_tier: Tier | None = None
    to_tier: Tier | None = None
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="the numbers that justify it; a PR without these cannot be reviewed",
    )
    payback_requests: float | None = None
    expected_remaining: float | None = None
    pr: str | None = None

    @property
    def pays_back(self) -> bool:
        """KNP-5 section 4. A cluster about to stop being asked about is not worth training."""
        if self.payback_requests is None or self.expected_remaining is None:
            return False
        return self.payback_requests < self.expected_remaining * PAYBACK_MARGIN


class DeclinedProposal(BaseModel):
    """A proposal that did not clear its gate, kept so the next window need not re-derive it.

    Not noise: a proposal declined five windows running is itself a signal that the cluster
    is not worth serving.
    """

    kind: ProposalKind
    cluster: str | None = None
    why: str
    windows_declined: int = 1


class Objective(BaseModel):
    """The one number the loop reduces, and the constraints it must not break."""

    cost_per_settled_request: float
    derived_share: float = Field(ge=0.0, le=1.0)
    quality_multiplier: float


class EvolveReport(BaseModel):
    """One report per run. The loop's only other output is PRs."""

    node: str
    window_start: datetime
    window_end: datetime
    objective: Objective
    previous: Objective | None = None
    clusters: list[ClusterStats] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    declined: list[DeclinedProposal] = Field(default_factory=list)

    def constraints_held(self) -> bool:
        """Cost may fall only if quality and verifiability did not (KNP-5 section 1)."""
        if self.previous is None:
            return True
        return (
            self.objective.derived_share >= self.previous.derived_share
            and self.objective.quality_multiplier >= Q_FLOOR
        )


#: Defaults from KNP-5. Overridable per node in kourob.yaml.
PAYBACK_MARGIN = 0.5
Q_FLOOR = 0.8
MIN_COVERAGE = 0.95
N_FEWSHOT = 50
N_DISTILL = 1000
N_RULE = 200


def evolve(node_dir: Any) -> EvolveReport:
    """Run one evolve pass. Reads the request log and receipts; writes proposals."""
    raise NotImplementedError("M4: see docs/protocols/knp-5-evolution.md")


__all__ = [
    "ClusterStats",
    "DeclinedProposal",
    "EvolveReport",
    "Objective",
    "Proposal",
    "ProposalKind",
    "evolve",
]
