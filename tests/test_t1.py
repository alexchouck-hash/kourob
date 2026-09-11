"""T1: the distilled student. Trained on settled answers, checked against gold.

Brief reference: sections 3.3 and 15. KNP-5 section 3.2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.loops.distill.calibrate import (
    calibrate_bar,
    compare_to_teacher,
    gold_rows,
    teacher_label,
)
from kourob.loops.distill.train import settled_examples, train_student
from kourob.loops.tend import apply_change, rollback
from kourob.testing import _scripted_grounded_runner, tennis_node_fixture
from kourob.tiers.t1_student import T1Student, load_student, similarity, tokens_of
from kourob.types import Tier

pytestmark = pytest.mark.m5


@pytest.fixture
def trained(tmp_path: Path) -> Path:
    return tennis_node_fixture(tmp_path)


# ---------------------------------------------------------------------------- the gate


def test_a_node_without_gold_cannot_enable_t1(tmp_path: Path) -> None:
    """Brief section 15, enforced: a student nobody can check learns the teacher's mistakes."""
    cell = tennis_node_fixture(tmp_path, with_gold=False)
    node = node_mod.open_node(cell)
    assert gold_rows(node) == []
    with pytest.raises(ValueError, match="gold"):
        T1Student.enable(node)
    assert not node_mod.open_node(cell).manifest.tier_enabled(Tier.T1)


def test_gold_goes_through_the_gate_and_dedupes(tmp_path: Path) -> None:
    cell = tennis_node_fixture(tmp_path, with_gold=False)
    node = node_mod.open_node(cell)
    lines = [
        json.dumps({"question": "who wins wimbledon", "label": "refuse"}),
        json.dumps({"question": "Who wins Wimbledon", "label": "refuse"}),  # dupe, case-insensitive
        json.dumps({"question": "", "label": "refuse"}),
        "not json",
    ]
    report = node.gate.ingest_gold(lines, task="scope_classifier")
    assert report.accepted == 1
    assert report.reasons == {"dedupe.exact": 1, "validate.missing_required": 1, "parse": 1}
    assert len(gold_rows(node_mod.open_node(cell))) == 1


# --------------------------------------------------------------------------- training


def test_training_reads_settled_answers_and_labels_them_by_the_rule_path(trained: Path) -> None:
    node = node_mod.open_node(trained)
    examples = settled_examples(node)
    assert examples, "the fixture asked and settled"
    labels = {e["label"] for e in examples}
    assert "rule:shot-lookup" in labels, "lookups a rule caught are kept, to place the boundary"
    assert "t3" in labels, "paraphrases a model answered are what T1 exists for"
    assert all(e["citations"] for e in examples)
    assert all(e["label"] == teacher_label(node, e["question"]) for e in examples)


def test_the_model_file_records_its_provenance_and_never_names_gold(trained: Path) -> None:
    student = load_student(trained)
    assert student is not None and student.version.startswith("student-s@0.1.")
    assert student.trained_from["sources"] == ["requests", "outcomes"]
    text = (trained / "tiers/t1/student.json").read_text(encoding="utf-8")
    assert "data/gold" not in text
    assert node_mod.open_node(trained).manifest.tier_enabled(Tier.T1)


def test_retraining_bumps_the_revision_and_keeps_the_bar(trained: Path) -> None:
    node = node_mod.open_node(trained)
    before = load_student(trained)
    train_student(node)
    after = load_student(trained)
    assert after.version != before.version
    assert after.bar == before.bar


# ------------------------------------------------------------------------- calibration


def test_the_student_tracks_the_teacher_per_class(trained: Path) -> None:
    scores = compare_to_teacher(node_mod.open_node(trained))
    assert scores.n >= 20
    assert scores.teacher_accuracy == 1.0, "gold was labelled by the teacher on unseen questions"
    assert scores.gap <= 0.02, (
        f"student {scores.student_accuracy:.3f}, weakest {scores.weakest_class}"
    )
    assert set(scores.per_class) >= {"rule:shot-lookup", "t3", "refuse"}
    assert all(row["student_accuracy"] >= 0.9 for row in scores.per_class.values()), (
        "matching on aggregate while collapsing a class is the classic distillation failure"
    )


def test_the_bar_is_the_lowest_that_hits_the_target_on_every_class(trained: Path) -> None:
    node = node_mod.open_node(trained)
    bar = calibrate_bar(node, target=0.95)
    assert 0.1 <= bar <= 1.0
    assert load_student(trained).bar == bar


def test_similarity_is_bounded_and_frame_gated() -> None:
    assert similarity(tokens_of("shot 1 of point p001"), tokens_of("shot 1 of point p001")) == 1.0
    assert similarity(set(), tokens_of("anything")) == 0.0
    assert (
        0
        < similarity(
            tokens_of("shot 1 of point p001 in match m"),
            tokens_of("shot 2 of point p001 in match m"),
        )
        < 1
    )


# ----------------------------------------------------------------------------- serving


def test_t1_answers_a_paraphrase_without_a_model_call(trained: Path) -> None:
    """The point of the tier: an answer the teacher settled, at a fraction of the cost."""
    node = node_mod.open_node(trained)
    calls_before = node.store.stats("calls")["rows"]

    answer = serve.answer(node, "which player hit shot 1 in point p001 of match ao-2026-f-01")

    assert answer.tier_used is Tier.T1, answer.rendered
    assert answer.citations and answer.is_grounded()
    assert node_mod.open_node(trained).store.stats("calls")["rows"] == calls_before
    receipt = next(
        r for r in node_mod.open_node(trained).ledger.records() if r["id"] == answer.receipt_id
    )
    assert receipt["model_version"].startswith("student-s@")
    assert receipt["determinism"] == "attested"
    assert 0 < receipt["cost_credits"] < 0.0001


def test_t1_declines_below_its_bar_and_the_cascade_falls_through(trained: Path) -> None:
    node = node_mod.open_node(trained)
    runner = _scripted_grounded_runner(node)
    answer = serve.answer(
        node, "tell me everything about the volley at the net in point p004", runner=runner
    )
    assert answer.tier_used in (Tier.T3, None), "not a near enough example for the student"


def test_t0_still_runs_before_t1(trained: Path) -> None:
    answer = serve.answer(node_mod.open_node(trained), "shot 1 of point p001 in match ao-2026-f-01")
    assert answer.tier_used is Tier.T0


# --------------------------------------------------------------------------- autonomy


def test_disable_and_rollback_switch_the_student_off_and_on(trained: Path) -> None:
    node = node_mod.open_node(trained)
    assert apply_change(node, "disable", "t1")
    assert not node_mod.open_node(trained).manifest.tier_enabled(Tier.T1)
    assert (trained / "tiers/t1/student.json").exists(), "the model file stays"

    assert apply_change(node_mod.open_node(trained), "enable", "t1")
    assert node_mod.open_node(trained).manifest.tier_enabled(Tier.T1)


def test_tend_proposes_rather_than_applies_t1_without_gold(tmp_path: Path) -> None:
    from kourob.loops.evolve import Proposal, ProposalKind
    from kourob.loops.tend import decide

    cell = tennis_node_fixture(tmp_path, with_gold=False)
    node = node_mod.open_node(cell)
    promotion = Proposal(kind=ProposalKind.PROMOTE, from_tier=Tier.T3, to_tier=Tier.T1, evidence={})
    (decision,) = decide(node, [promotion], level="A4", budget=10.0)
    assert decision.action == "propose" and "gold" in decision.why


def test_a_t1_promotion_applied_by_tend_can_be_rolled_back(trained: Path) -> None:
    from kourob.loops.evolve import Proposal, ProposalKind
    from kourob.loops.tend import Decision, _apply

    node = node_mod.open_node(trained)
    apply_change(node, "disable", "t1")
    promotion = Proposal(kind=ProposalKind.PROMOTE, from_tier=Tier.T3, to_tier=Tier.T1, evidence={})
    applied = _apply(node_mod.open_node(trained), Decision(promotion, "apply", "test"), "A2")
    assert applied is not None and applied.kind == "retrain" and applied.target == "t1"
    assert node_mod.open_node(trained).manifest.tier_enabled(Tier.T1)

    rollback(trained, applied.event_id)
    assert not node_mod.open_node(trained).manifest.tier_enabled(Tier.T1)
