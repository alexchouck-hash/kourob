"""Demand clustering and the evolve report.

Brief reference: KNP-5 sections 1, 2 and 8.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.loops.clustering import REFUSED, build_clusters, cluster_key
from kourob.loops.evolve import (
    EvolveReport,
    Objective,
    ProposalKind,
    demand_factor,
    evolve,
    past_reports,
)
from kourob.request_log import FRAME_WORDS, answer_shape, question_shape
from kourob.testing import node_with_events, note_check

pytestmark = pytest.mark.m4


@pytest.fixture
def cell(tmp_path: Path) -> Path:
    return node_with_events(tmp_path)


# ------------------------------------------------------------------------------- shapes


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("what is a bridge", "what is a cell"),
        ("What is a Bridge?", "what is a receipt"),
        ("how many aces did B hit", "how many winners did A hit"),
        ("shot 1 of point p001 in match ao-2026", "shot 3 of point p004 in match rg-2026"),
    ],
)
def test_questions_of_the_same_kind_share_a_shape(left: str, right: str) -> None:
    assert question_shape(left) == question_shape(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [("what is a bridge", "who wins wimbledon"), ("how many aces", "tell me about pruning")],
)
def test_questions_of_different_kinds_do_not(left: str, right: str) -> None:
    assert question_shape(left) != question_shape(right)


def test_the_shape_keeps_the_frame_and_drops_the_subject() -> None:
    """Getting this backwards is the obvious mistake: keep the subject and every topic
    becomes its own cluster, which is the same as not clustering."""
    assert question_shape("what is a bridge") == "what is *"
    assert "bridge" not in question_shape("what is a bridge")
    assert "us" not in FRAME_WORDS, "a frame word that is also a subject is worse than none"


def test_answer_shapes_separate_kinds_of_answer() -> None:
    assert answer_shape({"body": 1, "topic": 2}) == "{body,topic}"
    assert answer_shape([{"a": 1}]) == "[{a}]"
    assert answer_shape(None) == "none"


# ----------------------------------------------------------------------------- clusters


def test_the_decision_path_identifies_an_answered_cluster() -> None:
    """However the question was phrased: the same rule over the same schemas is one thing."""
    base = {
        "scope_result": "in_scope",
        "decided_by": "rule:note-lookup",
        "schemas": ["note.v1"],
        "tools": [],
        "answer_shape": "{body}",
    }
    assert cluster_key({**base, "shape": "what is *"}) == cluster_key(
        {**base, "shape": "tell me about *"}
    )


def test_a_refusal_clusters_on_the_question_frame() -> None:
    """There is no decision path to cluster on, and refusals are where declared scope and
    real demand disagree, so they must cluster on something."""
    key = cluster_key({"scope_result": "reject", "shape": "who *"})
    assert key.startswith(REFUSED)
    assert key != cluster_key({"scope_result": "reject", "shape": "how many *"})


def test_clustering_imports_no_embedding_machinery() -> None:
    """KNP-5 section 2: discrete features only. Checked structurally, not by intention."""
    source = (Path(__file__).resolve().parents[1] / "src/kourob/loops/clustering.py").read_text(
        encoding="utf-8"
    )
    imports = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    # Checked over imports rather than the whole file: the module says "no embeddings" in
    # its own docstring, and a substring search over prose finds the word it uses to
    # promise it will not do the thing.
    for forbidden in ("numpy", "sentence_transformers", "faiss", "torch", "sklearn", "openai"):
        assert not any(forbidden in line for line in imports), f"{forbidden} in {imports}"


def test_cost_per_settled_is_none_when_nothing_settled() -> None:
    """Not zero and not infinity. A cluster nobody settles has no cost *per settled
    request*, and inventing one lets it compete for promotion budget (ADR-0007)."""
    rows = [
        {
            "scope_result": "in_scope",
            "decided_by": "tier:T3",
            "schemas": "opinion.v1",
            "tools": "",
            "answer_shape": "{a}",
            "shape": "what is *",
            "cost_credits": 0.02,
            "receipt_id": f"rcpt_{i}",
            "request_hash": f"h{i}",
            "response_hash": f"r{i}",
            "citations": "",
            "citations_n": 0,
            "tiers_tried": "T3",
            "tier_used": "T3",
        }
        for i in range(5)
    ]
    (cluster,) = build_clusters(rows)
    assert cluster.cost_per_settled is None
    assert cluster.accept_rate is None
    assert cluster.settle_rate == 0.0
    assert not cluster.can_promote


def test_the_same_question_answered_differently_is_not_a_function() -> None:
    """`answer_entropy` above 1.0 is what disqualifies a cluster from T0 (KNP-5 3.3)."""

    def row(response: str) -> dict:
        return {
            "scope_result": "in_scope",
            "decided_by": "tier:T3",
            "schemas": "note.v1",
            "tools": "",
            "answer_shape": "{a}",
            "shape": "what is *",
            "cost_credits": 0.02,
            "receipt_id": "rcpt_x",
            "request_hash": "same-question",
            "response_hash": response,
            "citations": "evt_1",
            "citations_n": 1,
            "tiers_tried": "T3",
            "tier_used": "T3",
        }

    (stable,) = build_clusters([row("a"), row("a")])
    assert stable.answer_entropy == 1.0 and stable.is_function

    (unstable,) = build_clusters([row("a"), row("b")])
    assert unstable.answer_entropy == 2.0 and not unstable.is_function


# ------------------------------------------------------------------------ the objective


def test_demand_factor_is_zero_below_capacity_and_capped_above_it() -> None:
    assert demand_factor(50, 100, 3.0) == 0.0
    assert demand_factor(100, 100, 3.0) == 0.0
    assert demand_factor(140, 100, 3.0) == pytest.approx(0.4)
    assert demand_factor(10_000, 100, 3.0) == 3.0
    assert demand_factor(10, 0, 3.0) == 0.0


def test_constraints_fail_when_cost_falls_but_verifiability_does(cell: Path) -> None:
    """KNP-5 section 1: cost may fall only if quality and derived share did not."""
    now = datetime.now(UTC)
    before = Objective(cost_per_settled_request=0.0067, derived_share=0.34, quality_multiplier=0.94)
    after = Objective(cost_per_settled_request=0.0011, derived_share=0.19, quality_multiplier=0.94)
    report = EvolveReport(
        node="did:key:z6Mk", window_start=now, window_end=now, objective=after, previous=before
    )
    assert not report.constraints_held()

    kept = EvolveReport(
        node="did:key:z6Mk",
        window_start=now,
        window_end=now,
        objective=Objective(
            cost_per_settled_request=0.0011, derived_share=0.40, quality_multiplier=0.94
        ),
        previous=before,
    )
    assert kept.constraints_held()


# ---------------------------------------------------------------------------- the loop


def _ask(cell: Path, question: str, times: int = 1) -> None:
    for _ in range(times):
        serve.answer(node_mod.open_node(cell), question)


def test_evolve_writes_a_report_and_reads_the_last_one(cell: Path) -> None:
    _ask(cell, "what is a bridge", 3)
    first = evolve(cell)
    assert first.previous is None

    second = evolve(cell)
    assert second.previous is not None
    assert len(past_reports(cell)) == 2


def test_a_decline_carries_its_reason_and_survives_the_window(cell: Path) -> None:
    """KNP-5 section 8: declined is the loop's memory, not noise."""
    _ask(cell, "who wins wimbledon", 3)

    first = evolve(cell)
    drift = [d for d in first.declined if d.kind is ProposalKind.SCOPE_DRIFT]
    assert drift and drift[0].why
    assert drift[0].windows_declined == 1

    second = evolve(cell)
    drift2 = [d for d in second.declined if d.kind is ProposalKind.SCOPE_DRIFT]
    assert drift2[0].windows_declined == 2, (
        "next window must re-evaluate against fresh volume, not re-derive from nothing"
    )


def test_a_schema_that_settles_others_is_never_shed(cell: Path) -> None:
    """Found by running the loop and watching it propose shedding the schema that settles
    everything else (KNP-5 section 6)."""
    _ask(cell, "what is a bridge", 2)
    report = evolve(cell)

    shed = [p for p in report.proposals if p.kind is ProposalKind.SHED]
    assert "note_check.v1" not in [p.evidence.get("schema") for p in shed]

    (declined,) = [
        d for d in report.declined if d.kind is ProposalKind.SHED and d.cluster == "note_check.v1"
    ]
    assert "settles" in declined.why


def test_a_settled_answer_moves_the_objective(cell: Path) -> None:
    _ask(cell, "what is a bridge", 2)
    unsettled = evolve(cell)
    assert unsettled.objective.quality_multiplier == 0.5

    node_mod.open_node(cell).ingest(note_check(cell, "bridge", "accepted"))
    settled = evolve(cell)
    assert settled.objective.quality_multiplier > unsettled.objective.quality_multiplier
    assert settled.objective.derived_share == 1.0, "every answer came from a T0 rule"
