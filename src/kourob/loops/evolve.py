"""evolve: make this node cheaper at its own job without making it worse.

Brief reference: sections 5.2 and 6.1. Specified in docs/protocols/knp-5-evolution.md.
Decided in ADR-0005 (owed), ADR-0007, ADR-0008.

The loop does not optimise the node. It optimises **clusters of demand** discovered from
the request log, and it emits proposals, never silent changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from kourob import events as ev
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

    #: A split proposal carries the whole change, not a description of it (KNP-5 section 7).
    #: A reviewer should be able to read the child's manifest rather than imagine it.
    child_manifest: dict[str, Any] | None = None
    parent_scope_before: list[str] = Field(default_factory=list)
    parent_scope_after: list[str] = Field(default_factory=list)
    referral_rule: dict[str, Any] | None = None

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


N_QUARANTINE = 20
SCOPE_DRIFT_MIN = 25
REPORT_DIR = "logs/evolve"


def demand_factor(volume: int, capacity_window: int, max_surge: float) -> float:
    """Brief section 5.1. Zero below capacity; rises with load; capped at `max_surge`."""
    if capacity_window <= 0:
        return 0.0
    return max(0.0, min(max_surge, volume / capacity_window - 1.0))


def evolve(node_dir: Any, *, window: str = "30d", now: datetime | None = None) -> EvolveReport:
    """Run one evolve pass.

    Reads the request log, the ledger and quarantine. Writes a report and **proposals** -
    never a change. Applying a proposal is `kourob tend`'s job, and only within the node's
    autonomy level (KNP-7 section 2).
    """
    from kourob.ledger.outcomes import parse_window, read_outcomes, settlement_status
    from kourob.loops.clustering import REFUSED, build_clusters
    from kourob.node import open_node
    from kourob.types import Determinism

    node = open_node(node_dir)
    stamp = now or ev.now()
    span = parse_window(window) or timedelta(days=30)
    window_start = stamp - span

    rows = (
        node.store.scan("requests", order_by="id") if node.store.stats("requests")["rows"] else []
    )
    in_window = [r for r in rows if _within(r.get("ts"), window_start, stamp)]

    records = node.ledger.records()
    receipts = [r for r in records if r.get("kind", "receipt") == "receipt"]
    verdicts = {o.about: o.verdict for o in read_outcomes(node.ledger)}
    status = settlement_status(node.ledger, node.contracts, now=stamp)

    clusters = build_clusters(in_window, outcomes_by_receipt=verdicts)
    objective = Objective(
        cost_per_settled_request=_cost_per_settled(in_window, verdicts),
        derived_share=_derived_share(receipts, Determinism.DERIVED.value),
        quality_multiplier=status.quality_multiplier(),
    )

    report = EvolveReport(
        node=node.did,
        window_start=window_start,
        window_end=stamp,
        objective=objective,
        previous=_previous_objective(node.dir),
        clusters=clusters,
    )

    served = [c for c in clusters if not c.key.startswith(REFUSED)]
    _propose_demotions(report, node, verdicts)
    _propose_promotions(report, served, node=node, verdicts=verdicts)
    _propose_shed(report, node, in_window)
    _propose_split(report, node, served, len(in_window))
    _propose_from_quarantine(report, node)
    _propose_scope_drift(report, clusters)
    _carry_declines(report, node.dir)
    _write_report(node.dir, report)
    return report


# ------------------------------------------------------------------------------ proposals


def _propose_promotions(
    report: EvolveReport,
    clusters: list[ClusterStats],
    *,
    node: Any = None,
    verdicts: dict[str, Any] | None = None,
) -> None:
    """Move work down the ladder as evidence accumulates (KNP-5 section 3).

    Two paths. The rung below is proposed on a settled-example count. Independently, a
    cluster that has always been a function is **mined and replayed** for T0 straight from
    wherever it sits: exact replay is a stronger gate than any tolerance rung, and the
    ladder's no-skip rule exists to stop tolerance shortcuts, of which T0 has none.
    """
    overrides = (node.manifest.loops.get("evolve") or {}) if node is not None else {}
    n_rule = int(overrides.get("n_rule", N_RULE))
    for cluster in clusters:
        current = _dominant_tier(cluster)
        if current is None:
            continue

        if (
            node is not None
            and current is not Tier.T0
            and cluster.is_function
            and cluster.can_promote
            and round(cluster.settle_rate * cluster.volume) >= n_rule
        ):
            _propose_mined_rule(report, node, cluster, verdicts or {}, current)

        if not cluster.can_promote:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.PROMOTE,
                    cluster=cluster.key,
                    why=(
                        f"settle_rate 0 over {cluster.volume} requests: unverifiable work "
                        "does not get to be cheap (ADR-0007)"
                    ),
                )
            )
            continue

        target, threshold = _next_rung(current, node.manifest)
        if target is None:
            continue

        settled = round(cluster.settle_rate * cluster.volume)
        if settled < threshold:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.PROMOTE,
                    cluster=cluster.key,
                    why=(
                        f"{settled} settled of {threshold} needed for "
                        f"{current.value} to {target.value}"
                    ),
                )
            )
            continue

        if target is Tier.T0 and not cluster.is_function:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.PROMOTE,
                    cluster=cluster.key,
                    why=(
                        f"answer_entropy {cluster.answer_entropy:.2f}: the same question over "
                        "the same events gave different answers, so this is not a function"
                    ),
                )
            )
            continue

        report.proposals.append(
            Proposal(
                kind=ProposalKind.PROMOTE,
                cluster=cluster.key,
                from_tier=current,
                to_tier=target,
                evidence={
                    "volume": cluster.volume,
                    "settled": settled,
                    "accept_rate": cluster.accept_rate,
                    "answer_entropy": cluster.answer_entropy,
                    "schemas": cluster.schemas,
                },
            )
        )


def _propose_mined_rule(
    report: EvolveReport,
    node: Any,
    cluster: ClusterStats,
    verdicts: dict[str, Any],
    current: Tier,
) -> None:
    """Mine a T0 candidate and replay it (ADR-0008). Promote only if exact on every one."""
    from kourob.loops.distill.mine import mine_rule

    candidate = mine_rule(node.store, cluster, verdicts)
    if candidate is None:
        report.declined.append(
            DeclinedProposal(
                kind=ProposalKind.PROMOTE,
                cluster=cluster.key,
                why="a function, but not of one event with a field the question names: "
                "nothing to mine in v1",
            )
        )
        return
    evidence = {
        "rule": candidate.rule_id,
        "replay_exact_match": candidate.replay_exact_match,
        "coverage": candidate.coverage,
        "n": candidate.replayed,
        "misses": candidate.misses[:5],
        "rule_yaml": candidate.as_yaml(),
    }
    if not candidate.promotable:
        why = (
            f"replay_exact_match {candidate.replay_exact_match:.3f} over {candidate.covered} "
            f"covered: a rule that is not exact is not a function"
            if candidate.replay_exact_match < 1.0
            else f"coverage {candidate.coverage:.3f} below {MIN_COVERAGE}"
        )
        report.declined.append(
            DeclinedProposal(kind=ProposalKind.PROMOTE, cluster=cluster.key, why=why)
        )
        return
    report.proposals.append(
        Proposal(
            kind=ProposalKind.PROMOTE,
            cluster=cluster.key,
            from_tier=current,
            to_tier=Tier.T0,
            evidence=evidence,
            payback_requests=0.0,
            expected_remaining=float(cluster.volume),
        )
    )


def _propose_demotions(report: EvolveReport, node: Any, verdicts: dict[str, Any]) -> None:
    """One `corrected` outcome on a T0 answer disables its rule. Now, not next window.

    KNP-5 section 5 and ADR-0008: the rule's entire claim was that it is a function, and one
    counter-example disproves it. This is the one change the evolve loop makes itself rather
    than proposing, because it withdraws a privilege whose evidence stopped holding — the
    same mechanism as an autonomy demotion — and because it is trivially reversible: the
    file is renamed, not deleted.
    """
    from kourob.ledger.outcome import Verdict
    from kourob.tiers.t0_rules import RULES_DIR

    corrected: dict[str, list[str]] = {}
    for record in node.ledger.records():
        if record.get("kind", "receipt") != "receipt" or record.get("tier_used") != "T0":
            continue
        verdict = verdicts.get(record["id"])
        if verdict is not Verdict.CORRECTED:
            continue
        model = str(record.get("model_version") or "")
        if model.startswith("rule:"):
            corrected.setdefault(model.removeprefix("rule:"), []).append(record["id"])

    for rule_id, receipts in corrected.items():
        path = Path(node.dir) / RULES_DIR / f"{rule_id}.yaml"
        disabled = path.exists()
        if disabled:
            path.rename(path.with_suffix(".yaml.disabled"))
        report.proposals.append(
            Proposal(
                kind=ProposalKind.DEMOTE,
                cluster=f"rule:{rule_id}",
                from_tier=Tier.T0,
                to_tier=Tier.T1,
                evidence={
                    "rule": rule_id,
                    "counter_examples": len(receipts),
                    "receipts": receipts[:5],
                    "disabled": disabled,
                    "inverse": {"kind": "enable", "rule": rule_id},
                },
            )
        )


def _propose_shed(report: EvolveReport, node: Any, rows: list[dict[str, Any]]) -> None:
    """A node's size should track its demand, not its history (KNP-5 section 6).

    Three ways a schema earns its place, and only the first is obvious:

    1. requests cite it — it is being **read**;
    2. events arrive under it — it is being **written**, and a write nobody reads today may
       be the thing that settles an answer tomorrow;
    3. another contract names it in `settles_against` — it is **load-bearing for
       settlement**, and shedding it would quietly stop the node ever learning again.

    The third was found by running this loop and watching it propose shedding the schema
    that settles everything else.
    """
    read = {s for row in rows for s in _split_field(row.get("schemas"))}
    written = _written_schemas(node)
    settles_targets = {c.settles_against for c in node.contracts.values() if c.settles_against}

    for schema in node.manifest.scope.schemas:
        if schema in read:
            continue
        if schema in settles_targets:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.SHED,
                    cluster=schema,
                    why=(
                        f"{schema} answers nothing but settles answers about other schemas: "
                        "shedding it would stop this node learning"
                    ),
                )
            )
            continue
        if schema in written:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.SHED,
                    cluster=schema,
                    why=f"{schema} is being written even though nothing reads it yet",
                )
            )
            continue
        report.proposals.append(
            Proposal(
                kind=ProposalKind.SHED,
                cluster=schema,
                evidence={
                    "schema": schema,
                    "requests_in_window": 0,
                    "events_in_window": 0,
                    "window": str(node.manifest.prune.shed_window),
                    "refer_to": None,
                },
            )
        )


def _written_schemas(node: Any) -> set[str]:
    if node.store.stats("silver")["rows"] == 0:
        return set()
    rows = node.store.query("SELECT DISTINCT schema_ref FROM silver").to_pylist()
    return {str(r["schema_ref"]) for r in rows}


def _propose_split(
    report: EvolveReport, node: Any, clusters: list[ClusterStats], volume: int
) -> None:
    """Both conditions, or neither (KNP-5 section 7).

    High demand on one coherent cluster is a scaling problem, not a splitting problem. Two
    clusters at low volume are not worth two nodes. Either alone produces thrash.
    """
    pricing, policy = node.manifest.pricing, node.manifest.split
    factor = demand_factor(volume, pricing.capacity_window, pricing.max_surge)
    big = [c for c in clusters if volume and c.volume / volume >= policy.min_cluster_share]
    disjoint = _disjoint_pair(big)

    if factor <= policy.split_threshold:
        if disjoint:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.SPLIT,
                    why=(
                        f"demand_factor {factor:.2f} at or below split_threshold "
                        f"{policy.split_threshold}: two clusters is a shape, not a pressure"
                    ),
                )
            )
        return

    if not disjoint:
        report.declined.append(
            DeclinedProposal(
                kind=ProposalKind.SPLIT,
                why=(
                    f"demand_factor {factor:.2f} but no two clusters above "
                    f"{policy.min_cluster_share} touch disjoint schemas: a scaling problem, "
                    "not a splitting problem"
                ),
            )
        )
        return

    left, right = disjoint
    before = sorted(node.manifest.scope.schemas)
    report.proposals.append(
        Proposal(
            kind=ProposalKind.SPLIT,
            clusters=[left.key, right.key],
            parent_scope_before=before,
            parent_scope_after=sorted(set(before) - set(right.schemas)),
            child_manifest=_child_manifest(node, right),
            referral_rule={
                "pattern": "+".join(right.schemas),
                "schemas": right.schemas,
                "refer_to": "<child did:key, filled in when the child is created>",
            },
            evidence={
                "demand_factor": factor,
                "window_volume": volume,
                "shares": [left.volume / volume, right.volume / volume],
                "clusters": [
                    {"key": left.key, "schemas": left.schemas, "volume": left.volume},
                    {"key": right.key, "schemas": right.schemas, "volume": right.volume},
                ],
                "seam": "disjoint schemas",
            },
        )
    )


def _child_manifest(node: Any, cluster: ClusterStats) -> dict[str, Any]:
    """The child a split would create, as a manifest rather than a description of one.

    It **inherits the parent's promotion state** for its clusters (KNP-5 section 7): a child
    does not relearn what the parent already distilled. Autonomy resets to A0, because
    autonomy is earned by evidence and the child has none of its own yet (KNP-7 section 2).
    """
    parent = node.manifest
    name = "-".join(s.split(".")[0] for s in cluster.schemas) or "child"
    return {
        "kourob": parent.kourob,
        "identity": {
            "did": "",
            "name": f"{parent.identity.name}-{name}",
            "set": parent.identity.set,
        },
        "scope": {
            "summary": f"{', '.join(cluster.schemas)}, split out of {parent.identity.name}",
            "schemas": list(cluster.schemas),
            "entities": [],
            "capabilities": list(cluster.tools),
            "max_hops": parent.scope.max_hops,
        },
        "inherits": {
            "from": parent.identity.did,
            "tiers": {t.value: round(share, 3) for t, share in cluster.tier_mix.items()},
            "note": "tiers, rules and gold for these schemas move with the child",
        },
        "autonomy": {"level": "A0"},
        "pricing": {"base_cost": {t.value: c for t, c in parent.pricing.base_cost.items()}},
    }


def _propose_from_quarantine(report: EvolveReport, node: Any) -> None:
    """Repeated rejections are a schema proposal the node wrote for itself (brief 6.3)."""
    if node.store.stats("quarantine")["rows"] == 0:
        return
    counts: dict[str, int] = {}
    for row in node.store.scan("quarantine"):
        step = str(row.get("gate_step") or "?")
        counts[step] = counts.get(step, 0) + 1
    for step, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        if count >= N_QUARANTINE:
            report.proposals.append(
                Proposal(
                    kind=ProposalKind.RULE_FROM_QUARANTINE,
                    evidence={"gate_step": step, "count": count},
                )
            )
        elif count > 1:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.RULE_FROM_QUARANTINE,
                    why=(
                        f"{step} seen {count} times, under the {N_QUARANTINE} that make it "
                        "a pattern rather than a coincidence"
                    ),
                )
            )


def _propose_scope_drift(report: EvolveReport, clusters: list[ClusterStats]) -> None:
    """Sustained demand a node refuses is either somebody else's job or its own (KNP-1 7)."""
    from kourob.loops.clustering import REFUSED

    for cluster in clusters:
        if not cluster.key.startswith(REFUSED):
            continue
        if cluster.volume < SCOPE_DRIFT_MIN:
            report.declined.append(
                DeclinedProposal(
                    kind=ProposalKind.SCOPE_DRIFT,
                    cluster=cluster.key,
                    why=(
                        f"{cluster.volume} refusals, under the {SCOPE_DRIFT_MIN} that make "
                        "this demand rather than curiosity"
                    ),
                )
            )
            continue
        report.proposals.append(
            Proposal(
                kind=ProposalKind.SCOPE_DRIFT,
                cluster=cluster.key,
                evidence={
                    "refusals": cluster.volume,
                    "shape": cluster.key.split("|", 1)[-1],
                    "options": [
                        "declare an excludes entry naming who does own it",
                        "declare the scope and serve it",
                    ],
                },
            )
        )


# -------------------------------------------------------------------------------- helpers


def _within(ts: Any, start: datetime, end: datetime) -> bool:
    parsed = _parse_ts(ts)
    return parsed is not None and start <= parsed <= end


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _split_field(value: Any) -> list[str]:
    return [p for p in str(value or "").split(",") if p]


def _cost_per_settled(rows: list[dict[str, Any]], verdicts: dict[str, Any]) -> float:
    """The objective. Zero when nothing has settled, and that zero means "unmeasured".

    Cost per *settled* request, not per request: a node cannot reach the target by
    answering fast and wrong (ADR-0007).
    """
    settled = [r for r in rows if str(r.get("receipt_id") or "") in verdicts]
    if not settled:
        return 0.0
    return sum(float(r.get("cost_credits") or 0.0) for r in settled) / len(settled)


def _derived_share(receipts: list[dict[str, Any]], derived: str) -> float:
    """How much of what this node said a stranger could re-run (KNP-0 section 2)."""
    answered = [r for r in receipts if r.get("determinism")]
    if not answered:
        return 0.0
    return sum(1 for r in answered if r.get("determinism") == derived) / len(answered)


def _dominant_tier(cluster: ClusterStats) -> Tier | None:
    """Which tier is actually carrying this cluster."""
    if not cluster.tier_mix:
        return None
    return max(cluster.tier_mix.items(), key=lambda kv: kv[1])[0]


def _next_rung(current: Tier, manifest: Any = None) -> tuple[Tier | None, int]:
    """The rung below, and the settled-example count that unlocks it (KNP-5 section 3).

    A rung the manifest does not enable is skipped, with the *stricter* gate carried down:
    a node without a T2 goes T3 to T1 and needs T1's thousand settled examples, not T2's
    fifty. Skipping a tier is fine; skipping its evidence is not.
    """
    ladder = [
        (Tier.T2, N_FEWSHOT),
        (Tier.T1, N_DISTILL),
        (Tier.T0, N_RULE),
    ]
    order = [Tier.T3, Tier.T2, Tier.T1, Tier.T0]
    if current not in order or current is Tier.T0:
        return None, 0
    threshold = 0
    for tier, needed in ladder[order.index(current) :]:
        threshold = max(threshold, needed)
        # Only T2 can be absent from a node. T1 is disabled until it is *promoted to* -
        # that is what the promotion does - and its own gate (a gold set) is checked when
        # the proposal is applied, not here.
        if tier is Tier.T2 and manifest is not None and not manifest.tier_enabled(Tier.T2):
            continue
        return tier, threshold
    return None, 0


def _disjoint_pair(clusters: list[ClusterStats]) -> tuple[ClusterStats, ClusterStats] | None:
    """Two clusters that touch mostly different schemas, largest first.

    "Mostly" is "not at all" here. A seam that shares a schema is not a seam: both children
    would keep writing the same events and would have to talk constantly (KNP-8 section 3.1).
    """
    ranked = sorted(clusters, key=lambda c: -c.volume)
    for i, left in enumerate(ranked):
        for right in ranked[i + 1 :]:
            if left.schemas and right.schemas and not set(left.schemas) & set(right.schemas):
                return left, right
    return None


# ------------------------------------------------------------------------- report files


def report_dir(node_dir: Path | str) -> Path:
    return Path(node_dir) / REPORT_DIR


def past_reports(node_dir: Path | str) -> list[dict[str, Any]]:
    """Previous runs, oldest first. The loop's memory."""
    directory = report_dir(node_dir)
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def _previous_objective(node_dir: Path | str) -> Objective | None:
    reports = past_reports(node_dir)
    if not reports:
        return None
    try:
        return Objective.model_validate(reports[-1]["objective"])
    except (KeyError, ValueError):
        return None


def _carry_declines(report: EvolveReport, node_dir: Path | str) -> None:
    """A declined proposal is the loop's memory, not noise.

    Next window the same candidate is re-evaluated against fresh volume rather than
    re-derived from nothing, and one declined five windows running is itself a signal that
    the cluster is not worth serving (KNP-5 section 8).
    """
    history: dict[tuple[str, str | None], int] = {}
    for past in past_reports(node_dir):
        for entry in past.get("declined", []):
            key = (str(entry.get("kind")), entry.get("cluster"))
            history[key] = max(history.get(key, 0), int(entry.get("windows_declined", 1)))
    for declined in report.declined:
        declined.windows_declined = history.get((declined.kind.value, declined.cluster), 0) + 1


def _write_report(node_dir: Path | str, report: EvolveReport) -> Path:
    """One file per run. A document, not a table: nobody queries these, they read them."""
    directory = report_dir(node_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report.window_end.strftime('%Y%m%dT%H%M%S%f')}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def render(report: EvolveReport) -> str:
    """What `kourob loop run evolve` prints."""
    lines = [
        f"evolve {report.window_start:%Y-%m-%d} to {report.window_end:%Y-%m-%d}",
        f"  cost/settled  {report.objective.cost_per_settled_request:.6f}",
        f"  derived share {report.objective.derived_share:.2f}",
        f"  quality       {report.objective.quality_multiplier:.2f}",
        f"  constraints   {'held' if report.constraints_held() else 'BROKEN'}",
        "",
        f"clusters ({len(report.clusters)}):",
    ]
    for cluster in sorted(report.clusters, key=lambda c: -c.volume):
        cost = "-" if cluster.cost_per_settled is None else f"{cluster.cost_per_settled:.5f}"
        lines.append(
            f"  {cluster.volume:>5}  settle {cluster.settle_rate:.2f}  "
            f"entropy {cluster.answer_entropy:.2f}  cost/settled {cost}  {cluster.key[:52]}"
        )
    lines.append("")
    lines.append(f"proposals ({len(report.proposals)}):")
    for proposal in report.proposals:
        target = f" -> {proposal.to_tier.value}" if proposal.to_tier else ""
        lines.append(f"  {proposal.kind.value}{target}  {proposal.cluster or ''}")
        lines.append(f"      {proposal.evidence}")
    if report.declined:
        lines.append("")
        lines.append(f"declined ({len(report.declined)}):")
        for declined in report.declined:
            lines.append(
                f"  {declined.kind.value}  x{declined.windows_declined}  "
                f"{declined.cluster or ''}: {declined.why}"
            )
    return chr(10).join(lines)


__all__ = [
    "ClusterStats",
    "DeclinedProposal",
    "EvolveReport",
    "Objective",
    "Proposal",
    "ProposalKind",
    "demand_factor",
    "evolve",
    "past_reports",
    "render",
    "report_dir",
]
