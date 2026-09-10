"""Demand clustering: what this node is repeatedly being asked to do.

Brief reference: KNP-5 section 2.

The evolve loop does not optimise the node. It optimises **clusters of demand**, and this is
where they come from. Clustering is over discrete features — the decision path, the schemas
touched, the tools called, the answer shape, and for refusals the question frame. No
embeddings: requests are short and already typed, and an embedding would add a dependency,
a failure mode, and no accuracy.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from kourob.ledger.outcome import Verdict
from kourob.loops.evolve import ClusterStats
from kourob.request_log import RequestRecord
from kourob.types import Tier

__milestone__ = "M4"

REFUSED = "refused"


def cluster_key(record: dict[str, Any]) -> str:
    """Which cluster one request belongs to.

    For an **answered** request the decision path identifies the function: the same rule
    over the same schemas producing the same answer shape is one thing, however the question
    was phrased. For a **refused** request there is no decision path, so the question frame
    is all there is — and refusals are exactly where a node's declared scope and its real
    demand disagree, so they must cluster too.
    """
    if record.get("scope_result") != "in_scope":
        return f"{REFUSED}|{record.get('shape', '(empty)')}"
    parts = [
        str(record.get("decided_by") or "?"),
        "+".join(record.get("schemas") or []) or "-",
        "+".join(record.get("tools") or []) or "-",
        str(record.get("answer_shape") or "none"),
    ]
    return "|".join(parts)


@dataclass
class _Accumulator:
    """Per-cluster running totals. Kept separate from ClusterStats so the model stays a
    value object and the arithmetic stays here."""

    volume: int = 0
    cost: float = 0.0
    tiers: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    citations: int = 0
    schemas: set[str] = field(default_factory=set)
    tools: set[str] = field(default_factory=set)
    settled: int = 0
    accepted: int = 0
    settled_cost: float = 0.0
    #: (request_hash, cited events) -> the distinct responses seen for it. This is what
    #: `answer_entropy` measures: whether the answer has always been a function of its input.
    responses: dict[tuple[str, str], set[str]] = field(default_factory=lambda: defaultdict(set))


def build_clusters(
    requests: list[dict[str, Any]],
    *,
    outcomes_by_receipt: dict[str, Verdict] | None = None,
) -> list[ClusterStats]:
    """Group the request log into clusters and compute the statistics KNP-5 reasons over."""
    verdicts = outcomes_by_receipt or {}
    acc: dict[str, _Accumulator] = defaultdict(_Accumulator)

    for raw in requests:
        record = RequestRecord.from_row(raw)
        bucket = acc[cluster_key(record)]
        bucket.volume += 1
        bucket.cost += float(record.get("cost_credits") or 0.0)
        bucket.citations += int(record.get("citations_n") or 0)
        bucket.schemas.update(record.get("schemas") or [])
        bucket.tools.update(record.get("tools") or [])
        if record.get("tier_used"):
            bucket.tiers[str(record["tier_used"])] += 1

        signature = (
            str(record.get("request_hash") or ""),
            ",".join(sorted(record.get("citations") or [])),
        )
        bucket.responses[signature].add(str(record.get("response_hash") or ""))

        verdict = verdicts.get(str(record.get("receipt_id") or ""))
        if verdict is not None and verdict is not Verdict.UNRESOLVED:
            bucket.settled += 1
            bucket.settled_cost += float(record.get("cost_credits") or 0.0)
            if verdict is Verdict.ACCEPTED:
                bucket.accepted += 1

    return [_stats(key, bucket) for key, bucket in sorted(acc.items())]


def _stats(key: str, bucket: _Accumulator) -> ClusterStats:
    tier_mix: dict[Tier, float] = {}
    answered = sum(bucket.tiers.values())
    if answered:
        tier_mix = {Tier(name): count / answered for name, count in bucket.tiers.items()}

    return ClusterStats(
        key=key,
        volume=bucket.volume,
        tier_mix=tier_mix,
        # None, not zero and not infinity. A cluster nobody settles has no cost *per settled
        # request*, and inventing a number here would let it compete for promotion budget
        # against clusters that can actually be checked (ADR-0007).
        cost_per_settled=(bucket.settled_cost / bucket.settled) if bucket.settled else None,
        settle_rate=bucket.settled / bucket.volume if bucket.volume else 0.0,
        accept_rate=(bucket.accepted / bucket.settled) if bucket.settled else None,
        event_fanout=bucket.citations / bucket.volume if bucket.volume else 0.0,
        answer_entropy=_entropy(bucket),
        schemas=sorted(bucket.schemas),
        tools=sorted(bucket.tools),
    )


def _entropy(bucket: _Accumulator) -> float:
    """Distinct answers per distinct (question, event-set).

    1.0 means the cluster has always been a function of its inputs, and functions belong in
    T0 (KNP-5 section 3.3). Above 1.0 means the same question over the same events produced
    different answers, which is exactly what disqualifies it.
    """
    if not bucket.responses:
        return 1.0
    return sum(len(seen) for seen in bucket.responses.values()) / len(bucket.responses)


__all__ = ["REFUSED", "build_clusters", "cluster_key"]
