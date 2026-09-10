"""M1 acceptance criteria, written before the implementation.

Brief section 12, M1. These are marked xfail (strict, per pyproject) with the milestone in
the reason: CI stays green on M0, and the moment a feature lands the strict xfail turns
the pass into a failure, which forces the marker off in the PR that implements it.

Do not weaken a test to make it pass. Delete the marker, or leave it alone.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kourob.cli import app
from kourob.store.parquet_duckdb import ParquetDuckDBStore

pytestmark = pytest.mark.m1

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "gate_fixtures"

M1 = "M1 not implemented"


def _cell_with_shot_contract(node_dir: Path) -> None:
    """Init a cell and give it the fixture contract and its T0 rule.

    A freshly-inited cell owns the template's starter contract, not `shot.v1`. These tests
    are about the gate and the cascade, so they bring their own schema rather than leaning
    on whatever the template happens to ship.
    """
    assert runner.invoke(app, ["init", str(node_dir)]).exit_code == 0
    shutil.copy(FIXTURES / "schema.odcs.yaml", node_dir / "schemas" / "shot.odcs.yaml")
    shutil.copy(
        FIXTURES / "rules" / "shot-lookup.yaml",
        node_dir / "tiers" / "t0" / "rules" / "shot-lookup.yaml",
    )


def test_init_then_ingest_produces_silver_and_quarantine(node_dir: Path) -> None:
    """`kourob init demo && kourob ingest fixtures/events.jsonl` produces silver rows and a
    quarantine file with reasons for the malformed fixtures.

    Deliberately uses the fixtures `init` lays down rather than bringing its own: this is
    the out-of-the-box path in GOAL.md metric 1, and if it needs outside help it is not
    out-of-the-box.
    """
    assert runner.invoke(app, ["init", str(node_dir)]).exit_code == 0

    result = runner.invoke(
        app, ["ingest", str(node_dir / "fixtures" / "events.jsonl"), "--node", str(node_dir)]
    )
    assert result.exit_code == 0, result.output

    store = ParquetDuckDBStore(node_dir)
    assert store.stats("silver")["rows"] > 0, "ingest produced no silver rows"

    quarantined = store.scan("quarantine")
    assert quarantined, "the malformed fixtures produced no quarantine rows"
    assert all(row["reason"] for row in quarantined), "every quarantine row carries a reason"
    assert {row["gate_step"] for row in quarantined} >= {
        "validate.pattern",
        "validate.missing_required",
        "stamp.unknown_schema",
    }, "the starter fixtures should exercise several gate steps, not just one"


def test_gate_rejection_precision_and_recall() -> None:
    """Precision and recall of rejections >= 0.95 on evals/gate_fixtures/."""
    from kourob.gate import Gate

    gate = Gate.from_schema(FIXTURES / "schema.odcs.yaml")

    tp = fp = fn = 0
    for line in (FIXTURES / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        expected_reject = case["_expect"] == "reject"
        push = {k: v for k, v in case.items() if not k.startswith("_")}
        rejected = gate.check(push).rejected
        tp += expected_reject and rejected
        fp += (not expected_reject) and rejected
        fn += expected_reject and (not rejected)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    assert precision >= 0.95, f"rejection precision {precision:.3f}"
    assert recall >= 0.95, f"rejection recall {recall:.3f}"


def test_malformed_lines_are_rejected_at_the_parse_step() -> None:
    from kourob.gate import Gate

    gate = Gate.from_schema(FIXTURES / "schema.odcs.yaml")
    for line in (FIXTURES / "malformed.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        outcome = gate.check_raw(line)
        assert outcome.rejected
        assert outcome.gate_step == "parse", f"{line[:40]!r} rejected at {outcome.gate_step}"


def test_every_mcp_answer_carries_the_full_envelope(node_dir: Path) -> None:
    """Every answer over MCP includes data, rendered, citations, receipt_id.

    Including refusals: `data` is legitimately None when a node declines, which is why the
    invariant is about the envelope being complete, not about `data` being populated. What
    is never optional is `receipt_id`.
    """
    from kourob.ports.mcp import TOOLS, handle

    _cell_with_shot_contract(node_dir)
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])

    calls = [
        ("query", {"question": "shot 1 of point p001 in match ao-2026-f-01"}),
        ("query", {"question": "who will win wimbledon"}),  # a refusal is still an envelope
        ("get_page", {"page": "index"}),
        ("list_schemas", {}),
        ("nonsense", {}),  # an unknown tool is a refusal, not an exception
    ]
    for tool, args in calls:
        answer = handle(node_dir, tool, args)
        assert answer.rendered, f"{tool} produced no rendered form"
        assert isinstance(answer.citations, list)
        assert answer.receipt_id.startswith("rcpt_"), f"{tool} answered without a receipt"
        assert answer.is_grounded(), f"{tool} made a claim it cannot source"

    answered = handle(node_dir, "query", {"question": "shot 1 of point p001 in match ao-2026-f-01"})
    assert answered.data is not None
    assert answered.citations, "an in-scope answer cites the events behind it"

    assert set(TOOLS) == {"query", "ingest", "get_page", "list_schemas"}


def test_ledger_verify_passes_and_tampering_breaks_it(node_dir: Path) -> None:
    """`kourob ledger verify` passes; tampering with one receipt makes it fail."""
    from kourob.ledger.verify import tamper_for_test, verify

    _cell_with_shot_contract(node_dir)
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])
    runner.invoke(
        app, ["query", "shot 1 of point p001 in match ao-2026-f-01", "--node", str(node_dir)]
    )

    assert runner.invoke(app, ["ledger", "verify", "--node", str(node_dir)]).exit_code == 0
    assert verify(node_dir).ok

    tamper_for_test(node_dir, index=0, field="price_credits", value=0.0)

    assert runner.invoke(app, ["ledger", "verify", "--node", str(node_dir)]).exit_code != 0
    report = verify(node_dir)
    assert not report.ok
    assert report.first_break is not None


def test_a_t0_answerable_question_never_reaches_t3(node_dir: Path) -> None:
    """Assert via the receipt's tier_used, not via timing or logs."""
    from kourob.ledger.verify import read_receipts
    from kourob.types import Tier

    _cell_with_shot_contract(node_dir)
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])

    # An exact lookup the T0 SQL view answers: it must not spend a frontier token.
    result = runner.invoke(
        app, ["query", "shot 1 of point p001 in match ao-2026-f-01", "--node", str(node_dir)]
    )
    assert result.exit_code == 0

    receipt = read_receipts(node_dir)[-1]
    assert receipt.tier_used == Tier.T0, f"answered at {receipt.tier_used}, expected T0"
