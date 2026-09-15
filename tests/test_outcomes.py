"""Outcomes: the record that says whether an answer held up.

Brief reference: KNP-2 section 6, ADR-0007.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.ledger.chain import signed_view
from kourob.ledger.outcome import OutcomeSource, Verdict
from kourob.ledger.outcomes import (
    OutcomeError,
    outcomes_for,
    parse_window,
    read_outcomes,
    settle_key,
    settlement_status,
    submit,
)
from kourob.ledger.receipt import SIGNED_FIELDS as RECEIPT_FIELDS
from kourob.ledger.verify import trace, verify

pytestmark = pytest.mark.m4


@pytest.fixture
def cell(tmp_path: Path):
    target = tmp_path / "cell"
    node_mod.init(target, scope="the KouroB design, as notes")
    node_mod.open_node(target).ingest(target / "fixtures" / "events.jsonl")
    return node_mod.open_node(target)


def _answer(cell, question: str = "what is a bridge"):
    return serve.answer(node_mod.open_node(cell.dir), question)


def _check(cell, topic: str, verdict: str, minutes_ago: int = 5) -> Path:
    ts = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    path = cell.dir / f"check-{topic}-{verdict}.jsonl"
    path.write_text(
        json.dumps({"schema_ref": "note_check.v1", "topic": topic, "verdict": verdict, "ts": ts})
        + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------- the record


def test_an_outcome_never_edits_the_receipt_it_judges(cell) -> None:
    """ADR-0007: the wrong answer stays in the chain with a correction pointing at it."""
    answer = _answer(cell)
    node = node_mod.open_node(cell.dir)
    before = next(r for r in node.ledger.records() if r["id"] == answer.receipt_id)
    before_view = signed_view(before, RECEIPT_FIELDS)

    submit(
        node.ledger,
        answer.receipt_id,
        verdict=Verdict.CORRECTED,
        evidence=["evt_whatever"],
        note="wrong",
    )

    after = next(
        r for r in node_mod.open_node(cell.dir).ledger.records() if r["id"] == answer.receipt_id
    )
    # Compared over the signed fields rather than the whole row: receipts and outcomes share
    # one Parquet table, so reading a receipt back after an outcome exists brings null
    # columns that belong to the other record kind. Those are storage, not content.
    assert signed_view(after, RECEIPT_FIELDS) == before_view
    assert after["sig"] == before["sig"]
    assert verify(cell.dir).ok


def test_a_correction_must_say_what_was_true(cell) -> None:
    answer = _answer(cell)
    node = node_mod.open_node(cell.dir)
    with pytest.raises(OutcomeError, match="point at what was true"):
        submit(node.ledger, answer.receipt_id, verdict=Verdict.CORRECTED)


def test_a_stranger_is_recorded_at_the_lowest_weight_not_refused(cell) -> None:
    """A third party noticing an error is useful even when it cannot be trusted."""
    answer = _answer(cell)
    node = node_mod.open_node(cell.dir)
    outcome = submit(
        node.ledger,
        answer.receipt_id,
        verdict=Verdict.REJECTED,
        source=OutcomeSource.HUMAN,
        by="user:someone-else",
    )
    assert outcome.source is OutcomeSource.CALLER
    assert outcome.weight < 1.0


def test_an_outcome_cannot_judge_an_outcome(cell) -> None:
    answer = _answer(cell)
    node = node_mod.open_node(cell.dir)
    outcome = submit(node.ledger, answer.receipt_id, verdict=Verdict.ACCEPTED)
    with pytest.raises(OutcomeError, match="not a receipt"):
        submit(node_mod.open_node(cell.dir).ledger, outcome.id, verdict=Verdict.ACCEPTED)


def test_an_unknown_receipt_is_refused(cell) -> None:
    with pytest.raises(OutcomeError, match="no receipt"):
        submit(cell.ledger, "rcpt_nope", verdict=Verdict.ACCEPTED)


# -------------------------------------------------------------------------- the chain


def test_the_chain_verifies_with_receipts_and_outcomes_interleaved(cell) -> None:
    """The bug this test exists for: ids are prefixed, so `outc_` sorts before `rcpt_`.

    Ordering the chain by id put every outcome before every receipt and broke `prev` the
    moment a node recorded its first outcome. The chain is ordered by an explicit `seq`.
    """
    first = _answer(cell, "what is a bridge")
    submit(node_mod.open_node(cell.dir).ledger, first.receipt_id, verdict=Verdict.ACCEPTED)
    second = _answer(cell, "what is a cell")
    submit(node_mod.open_node(cell.dir).ledger, second.receipt_id, verdict=Verdict.ACCEPTED)

    report = verify(cell.dir)
    assert report.ok, report.first_break
    assert report.receipts == 2
    assert report.outcomes == 2

    kinds = [r["kind"] for r in node_mod.open_node(cell.dir).ledger.records()]
    assert kinds == ["receipt", "outcome", "receipt", "outcome"]


def test_trace_shows_an_answer_and_its_correction_from_one_receipt_id(cell) -> None:
    answer = _answer(cell)
    node_mod.open_node(cell.dir).ingest(_check(cell, "bridge", "corrected"))

    chain = trace(cell.dir, answer.receipt_id)
    assert len(chain.outcomes) == 1
    assert chain.outcomes[0]["verdict"] == "corrected"
    assert "corrected by reality" in chain.render()


# ---------------------------------------------------------------------------- settling


def test_a_later_fact_settles_an_earlier_answer(cell) -> None:
    """`source: reality` — the only outcome source that is free, honest and unarguable."""
    answer = _answer(cell, "what is a bridge")

    node = node_mod.open_node(cell.dir)
    _report, settlements = node.ingest(_check(cell, "bridge", "corrected"))

    assert len(settlements) == 1
    (outcome,) = outcomes_for(node_mod.open_node(cell.dir).ledger, answer.receipt_id)
    assert outcome.verdict is Verdict.CORRECTED
    assert outcome.source is OutcomeSource.REALITY
    assert outcome.weight == 1.0
    assert outcome.evidence, "a settlement points at the event that settled it"
    assert outcome.latency_s is not None


def test_settlement_only_touches_answers_about_the_same_subject(cell) -> None:
    bridge = _answer(cell, "what is a bridge")
    cell_answer = _answer(cell, "what is a cell")

    node_mod.open_node(cell.dir).ingest(_check(cell, "bridge", "accepted"))

    ledger = node_mod.open_node(cell.dir).ledger
    assert len(outcomes_for(ledger, bridge.receipt_id)) == 1
    assert outcomes_for(ledger, cell_answer.receipt_id) == []


def test_the_same_fact_arriving_twice_is_not_two_outcomes(cell) -> None:
    answer = _answer(cell, "what is a bridge")
    node_mod.open_node(cell.dir).ingest(_check(cell, "bridge", "accepted", minutes_ago=9))
    node_mod.open_node(cell.dir).ingest(_check(cell, "bridge", "accepted", minutes_ago=8))

    assert len(outcomes_for(node_mod.open_node(cell.dir).ledger, answer.receipt_id)) == 1


def test_a_receipt_with_no_subject_is_never_settled(cell) -> None:
    """A T3 answer to a free-text question has no subject the node can name.

    That is a real limit of the design, not an oversight, and the receipt simply stays
    pending rather than being settled by something that happens to share a topic.
    """
    node = node_mod.open_node(cell.dir)
    answer = serve.answer(node, "what is a bridge")
    receipt = next(r for r in node.ledger.records() if r["id"] == answer.receipt_id)
    assert receipt["settle_key"] == settle_key("note.v1", {"topic": "bridge"})

    unmatched = serve.answer(node_mod.open_node(cell.dir), "zzzz qqqq nothing")
    record = next(
        r for r in node_mod.open_node(cell.dir).ledger.records() if r["id"] == unmatched.receipt_id
    )
    assert record["settle_key"] is None


def test_settle_keys_are_hashed_not_stored_in_the_clear() -> None:
    """A receipt may be published; its subject may not be publishable (KNP-2 section 6.2)."""
    key = settle_key("note.v1", {"topic": "bridge"})
    assert key.startswith("sha256:")
    assert "bridge" not in key
    assert key == settle_key("note.v1", {"topic": "bridge"})
    assert key != settle_key("note.v1", {"topic": "cell"})


# --------------------------------------------------------------------------- reporting


def test_unresolved_is_computed_never_written(cell) -> None:
    """Appending a record to say nothing happened would manufacture evidence from absence."""
    _answer(cell)
    node = node_mod.open_node(cell.dir)

    fresh = settlement_status(node.ledger, node.contracts)
    assert fresh.pending == 1 and fresh.unresolved == 0

    later = settlement_status(
        node.ledger, node.contracts, now=datetime.now(UTC) + timedelta(days=31)
    )
    assert later.unresolved == 1 and later.pending == 0
    assert read_outcomes(node.ledger) == [], "nothing was written to say nothing happened"


def test_a_node_nobody_checks_cannot_keep_a_quality_premium(cell) -> None:
    """KNP-3 section 3: unresolved counts against the denominator."""
    for question in ("what is a bridge", "what is a cell", "what is a receipt"):
        _answer(cell, question)
    node = node_mod.open_node(cell.dir)

    stale = settlement_status(
        node.ledger, node.contracts, now=datetime.now(UTC) + timedelta(days=31)
    )
    assert stale.unresolved == 3
    assert stale.quality_multiplier() == 0.5, "drifts to q_min, not a default of 1.0"
    assert stale.accept_rate is None, "an unmeasured node is not a perfect one"


def test_accepted_answers_earn_the_premium(cell) -> None:
    for topic, question in (("bridge", "what is a bridge"), ("cell", "what is a cell")):
        _answer(cell, question)
        node_mod.open_node(cell.dir).ingest(_check(cell, topic, "accepted"))

    node = node_mod.open_node(cell.dir)
    status = settlement_status(node.ledger, node.contracts)
    assert status.settled == 2
    assert status.accept_rate == 1.0
    assert status.quality_multiplier() == 1.0


@pytest.mark.parametrize(
    ("text", "days"),
    [("7d", 7), ("30d", 30), ("2w", 14), ("12h", 0.5)],
)
def test_windows_parse(text: str, days: float) -> None:
    assert parse_window(text) == timedelta(days=days)


def test_an_undeclared_window_means_never_settles() -> None:
    assert parse_window(None) is None
    with pytest.raises(ValueError, match="not a duration"):
        parse_window("soon")
