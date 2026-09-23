"""The shadow teacher: T3 audits a budgeted sample of cheap-tier answers (ADR-0011).

Disagreement is a signal and agreement is not a label. ADR-0007 rejected treating tier
agreement as correctness because it cannot catch a mistake both tiers make. So a dispute is
recorded, at the lowest weight, as a `teacher` outcome that never settles anything. It
blocks promotion until reality or a human speaks. Agreement only makes the next audit in
that cluster less likely.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob import serve
from kourob.ledger.chain import RECORD_OUTCOME
from kourob.ledger.outcome import OutcomeSource, Verdict
from kourob.ledger.outcomes import outcomes_for, settlement_status, settling_outcomes
from kourob.loops.evolve import ProposalKind, evolve
from kourob.loops.shadow import MIN_RATE, SHADOW_TABLE, run_shadow, sample_rate
from kourob.runner import Runner
from kourob.runner.adapters import LocalAdapter
from kourob.testing import node_with_events, note_check, synthetic_request_log
from kourob.types import Tier

pytestmark = pytest.mark.m4


@pytest.fixture
def cell(tmp_path: Path) -> Path:
    """The starter cell, plus a second note that mentions bridges.

    Its hand-written rule answers "what is a bridge" at T0 from the `bridge` note. The
    `referral` note is one T3 also retrieves for that question, so a teacher citing it is
    a grounded disagreement rather than a fabrication T3 would drop.
    """
    target = node_with_events(tmp_path)
    extra = target / "referral.jsonl"
    extra.write_text(
        json.dumps(
            {
                "schema_ref": "note.v1",
                "topic": "referral",
                "body": "A referral names the node to ask instead; a bridge asks it for you.",
                "ts": "2026-09-02T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    node_mod.open_node(target).ingest(extra)
    return target


def _note_id(node_dir: Path, topic: str) -> str:
    node = node_mod.open_node(node_dir)
    return next(
        r["id"] for r in node.store.scan("silver") if (r.get("payload") or {}).get("topic") == topic
    )


def _teacher(node_dir: Path, *, cites: str | None, confidence: float = 0.9) -> Runner:
    """A T3 stand-in that cites the note on one topic, or declines."""
    node = node_mod.open_node(node_dir)
    citations = [_note_id(node_dir, cites)] if cites else []
    reply = json.dumps(
        {"answer": "per the notes", "citations": citations, "confidence": confidence}
    )
    return Runner(
        node.manifest,
        store=node.store,
        adapters={"local": LocalAdapter.scripted([], fallback=lambda _prompt: reply)},
    )


def _ask(node_dir: Path, question: str) -> str:
    answer = serve.answer(node_mod.open_node(node_dir), question)
    assert answer.tier_used == Tier.T0
    return answer.receipt_id


# ------------------------------------------------------------------------ the verdicts


def test_agreement_writes_no_outcome(cell: Path) -> None:
    receipt = _ask(cell, "what is a bridge")

    report = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=1.0)

    assert [a.verdict for a in report.audits] == ["agree"]
    assert outcomes_for(node_mod.open_node(cell).ledger, receipt) == []


def test_a_dispute_is_a_teacher_outcome_pointing_at_what_the_teacher_cited(cell: Path) -> None:
    receipt = _ask(cell, "what is a bridge")

    report = run_shadow(cell, runner=_teacher(cell, cites="referral"), budget_credits=1.0)

    assert [a.verdict for a in report.audits] == ["dispute"]
    (outcome,) = outcomes_for(node_mod.open_node(cell).ledger, receipt)
    assert outcome.source is OutcomeSource.TEACHER
    assert outcome.verdict is Verdict.REJECTED
    assert outcome.evidence == [_note_id(cell, "referral")]


def test_a_teacher_that_declines_abstains(cell: Path) -> None:
    receipt = _ask(cell, "what is a bridge")

    report = run_shadow(cell, runner=_teacher(cell, cites=None), budget_credits=1.0)

    assert [a.verdict for a in report.audits] == ["abstain"]
    assert outcomes_for(node_mod.open_node(cell).ledger, receipt) == []


# --------------------------------------------------------------- a dispute never settles


def test_a_dispute_does_not_count_as_settlement(cell: Path) -> None:
    _ask(cell, "what is a bridge")
    run_shadow(cell, runner=_teacher(cell, cites="referral"), budget_credits=1.0)

    node = node_mod.open_node(cell)
    assert settlement_status(node.ledger, node.contracts).settled == 0
    assert settling_outcomes(node.ledger) == []


def test_reality_still_settles_a_disputed_answer(cell: Path) -> None:
    receipt = _ask(cell, "what is a bridge")
    run_shadow(cell, runner=_teacher(cell, cites="referral"), budget_credits=1.0)

    node_mod.open_node(cell).ingest(note_check(cell, "bridge", "accepted"))

    settled = [o for o in settling_outcomes(node_mod.open_node(cell).ledger) if o.about == receipt]
    assert [o.verdict for o in settled] == [Verdict.ACCEPTED]
    assert settled[0].source is OutcomeSource.REALITY


# ---------------------------------------------------------------- what gets audited


def test_each_answer_is_audited_once(cell: Path) -> None:
    _ask(cell, "what is a bridge")
    run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=1.0)

    again = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=1.0)

    assert again.audits == []
    assert len(node_mod.open_node(cell).store.scan(SHADOW_TABLE)) == 1


def test_settled_answers_refusals_and_model_answers_are_not_audited(cell: Path) -> None:
    _ask(cell, "what is a bridge")
    node_mod.open_node(cell).ingest(note_check(cell, "bridge", "accepted"))
    serve.answer(node_mod.open_node(cell), "who wins wimbledon")  # refused or model-answered

    report = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=1.0)

    assert report.audits == []


def test_an_unreachable_teacher_audits_nothing_and_leaves_the_answer_owed(cell: Path) -> None:
    """No model is not an abstention. Recording it would retire the answer unaudited."""
    _ask(cell, "what is a bridge")
    node = node_mod.open_node(cell)

    class Unreachable(LocalAdapter):
        def available(self) -> bool:
            return False

    down = Runner(node.manifest, store=node.store, adapters={"local": Unreachable(offline=True)})

    report = run_shadow(cell, runner=down, budget_credits=1.0)

    assert report.unavailable
    assert report.audits == []
    later = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=1.0)
    assert [a.verdict for a in later.audits] == ["agree"]


def test_a_zero_budget_audits_nothing(cell: Path) -> None:
    _ask(cell, "what is a bridge")

    report = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=0.0)

    assert report.audits == []
    assert report.exhausted


# -------------------------------------------------------------------- the sample rate


def test_the_sample_rate_falls_with_agreement_and_has_a_floor() -> None:
    rates = [sample_rate(agreed) for agreed in range(100)]
    assert rates[0] == 1.0
    assert all(later <= earlier for earlier, later in pairwise(rates))
    assert rates[-1] == MIN_RATE


def test_agreement_thins_the_sample_and_a_dispute_restores_it(
    cell: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The draw is pinned so the arithmetic is exact: 0.3 clears rates 1, 1/2 and 1/3."""
    from kourob.loops import shadow

    for _ in range(10):
        _ask(cell, "what is a bridge")
    monkeypatch.setattr(shadow, "_draw", lambda _receipt: 0.3)
    agreeing = run_shadow(cell, runner=_teacher(cell, cites="bridge"), budget_credits=10.0)
    assert [a.rate for a in agreeing.audits] == [1.0, 0.5, pytest.approx(1 / 3)]

    # A draw under the floor is sampled however thin the cluster: the floor is what keeps
    # watching a rule that has been right for a long time.
    monkeypatch.setattr(shadow, "_draw", lambda _receipt: MIN_RATE / 2)
    disputing = run_shadow(cell, runner=_teacher(cell, cites="referral"), budget_credits=10.0)
    assert disputing.audits[0].rate == 0.25
    assert disputing.audits[0].verdict == "dispute"
    assert {a.rate for a in disputing.audits[1:]} == {1.0}, "after a dispute, audit everything"
    assert len(disputing.audits) == 10 - 3


# ------------------------------------------------------------------ what a dispute does


def _add_teacher_dispute(node_dir: Path) -> None:
    """A dispute on one unsettled answer, as the shadow loop would write it.

    Unsettled on purpose: a receipt reality already settled is not disputed, because the
    later fact outranks the teacher (`shadow.disputed_receipts`).
    """
    from kourob.ledger.outcomes import submit

    node = node_mod.open_node(node_dir)
    settled = {o.about for o in settling_outcomes(node.ledger)}
    receipt = next(
        r
        for r in node.ledger.records()
        if r.get("kind", "receipt") == "receipt" and r["id"] not in settled
    )
    submit(
        node.ledger,
        receipt["id"],
        verdict=Verdict.REJECTED,
        source=OutcomeSource.TEACHER,
        evidence=[],
        note="teacher disputed",
    )


def test_a_disputed_cluster_does_not_promote(tmp_path: Path) -> None:
    target = synthetic_request_log(
        tmp_path, clusters={"note.v1": 1.0}, tier=Tier.T3, settle_rate=0.95
    )
    manifest = node_mod.open_node(target).manifest
    manifest.tiers["t2"].enabled = True  # so a hundred settled answers earn T3 to T2
    manifest_mod.save(target, manifest)
    before = evolve(target)
    assert any(p.kind is ProposalKind.PROMOTE for p in before.proposals), (
        "the fixture must promote without a dispute, or this test proves nothing"
    )

    _add_teacher_dispute(target)
    after = evolve(target)

    assert not any(p.kind is ProposalKind.PROMOTE for p in after.proposals)
    declined = [d for d in after.declined if d.kind is ProposalKind.PROMOTE]
    assert any("teacher" in d.why for d in declined)


def test_a_teacher_outcome_is_on_the_chain(cell: Path) -> None:
    """Provenance: a caller can see that the node's own teacher disputed an answer."""
    receipt = _ask(cell, "what is a bridge")
    run_shadow(cell, runner=_teacher(cell, cites="referral"), budget_credits=1.0)

    records: list[dict[str, Any]] = node_mod.open_node(cell).ledger.records()
    (record,) = [r for r in records if r.get("kind") == RECORD_OUTCOME and r["about"] == receipt]
    assert record["source"] == "teacher"
