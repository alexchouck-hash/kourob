"""A model-tier answer is settled by what it cited (ADR-0010).

Brief reference: KNP-2 sections 2.1 and 6.2. STATUS weakness #5.

T0 names its subject by binding the question. T2 and T3 cannot, but they cite silver events,
and a cited event's contract says what settles it. When the citations name exactly one
subject, the receipt carries that subject's key and a later fact settles the answer exactly
as it would a rule's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.ledger.outcome import OutcomeSource, Verdict
from kourob.ledger.outcomes import outcomes_for, settle_key, settle_key_from_citations
from kourob.runner import Runner
from kourob.runner.adapters import LocalAdapter
from kourob.testing import note_check
from kourob.tiers.t0_rules import RULES_DIR

pytestmark = pytest.mark.m4


@pytest.fixture
def t3cell(tmp_path: Path) -> Path:
    """The starter cell with its hand-written rule disabled, so the model has to answer."""
    target = tmp_path / "cell"
    node_mod.init(target, scope="the KouroB design, as notes")
    for rule in (target / RULES_DIR).glob("*.yaml"):
        rule.rename(rule.with_suffix(".yaml.disabled"))
    node_mod.open_node(target).ingest(target / "fixtures" / "events.jsonl")
    return target


def _note_ids(node: Any, *topics: str) -> list[str]:
    rows = node.store.scan("silver")
    by_topic = {
        (r.get("payload") or {}).get("topic"): r["id"]
        for r in rows
        if r.get("schema_ref") == "note.v1"
    }
    return [by_topic[t] for t in topics]


def _citing(node: Any, citations: list[str]) -> Runner:
    """A T3 stand-in that answers and cites exactly the events it is told to."""
    reply = json.dumps({"answer": "as the notes say", "citations": citations, "confidence": 0.9})
    return Runner(
        node.manifest,
        store=node.store,
        adapters={"local": LocalAdapter.scripted([], fallback=lambda _prompt: reply)},
    )


def _receipt(node_dir: Path, receipt_id: str) -> dict[str, Any]:
    node = node_mod.open_node(node_dir)
    return next(r for r in node.ledger.records() if r["id"] == receipt_id)


def test_a_t3_answer_citing_one_note_carries_that_notes_key(t3cell: Path) -> None:
    node = node_mod.open_node(t3cell)
    runner = _citing(node, _note_ids(node, "bridge"))

    answer = serve.answer(node, "tell me how a bridge works", runner=runner)

    assert answer.tier_used == "T3"
    receipt = _receipt(t3cell, answer.receipt_id)
    assert receipt["settle_key"] == settle_key("note.v1", {"topic": "bridge"})


def test_a_later_fact_settles_the_t3_answer_from_reality(t3cell: Path) -> None:
    """The point of the key: the tier most in need of correction can now be corrected."""
    node = node_mod.open_node(t3cell)
    answer = serve.answer(
        node, "tell me how a bridge works", runner=_citing(node, _note_ids(node, "bridge"))
    )

    node_mod.open_node(t3cell).ingest(note_check(t3cell, "bridge", "corrected"))

    (outcome,) = outcomes_for(node_mod.open_node(t3cell).ledger, answer.receipt_id)
    assert outcome.source is OutcomeSource.REALITY
    assert outcome.verdict is Verdict.CORRECTED


def test_citations_naming_two_subjects_leave_the_key_null(t3cell: Path) -> None:
    """A fact about one of them does not say whether an answer about both held up."""
    node = node_mod.open_node(t3cell)
    runner = _citing(node, _note_ids(node, "bridge", "receipt"))

    answer = serve.answer(node, "how does a bridge relate to a receipt", runner=runner)

    assert answer.tier_used == "T3"
    assert _receipt(t3cell, answer.receipt_id)["settle_key"] is None


def test_two_citations_about_one_subject_still_settle(t3cell: Path) -> None:
    node = node_mod.open_node(t3cell)
    extra = t3cell / "more-bridge.jsonl"
    extra.write_text(
        json.dumps(
            {
                "schema_ref": "note.v1",
                "topic": "bridge",
                "body": "A bridge hands back the direct route with its answer.",
                "ts": "2026-09-02T09:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    node.ingest(extra)
    node = node_mod.open_node(t3cell)
    bridge_ids = [
        r["id"]
        for r in node.store.scan("silver")
        if (r.get("payload") or {}).get("topic") == "bridge"
    ]
    assert len(bridge_ids) == 2

    key = settle_key_from_citations(node.contracts, node.store, bridge_ids)

    assert key == settle_key("note.v1", {"topic": "bridge"})


def test_citations_with_no_settling_contract_leave_the_key_null(t3cell: Path) -> None:
    node = node_mod.open_node(t3cell)
    assert settle_key_from_citations(node.contracts, node.store, []) is None
    assert settle_key_from_citations(node.contracts, node.store, ["evt_not_in_silver"]) is None


def test_a_rules_own_key_is_never_overridden(tmp_path: Path) -> None:
    """T0 binds its subject from the question; that is more specific than any citation."""
    target = tmp_path / "cell"
    node_mod.init(target, scope="the KouroB design, as notes")
    node_mod.open_node(target).ingest(target / "fixtures" / "events.jsonl")

    answer = serve.answer(node_mod.open_node(target), "what is a bridge")

    assert answer.tier_used == "T0"
    assert _receipt(target, answer.receipt_id)["settle_key"] == settle_key(
        "note.v1", {"topic": "bridge"}
    )
