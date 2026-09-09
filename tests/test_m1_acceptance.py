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
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kourob.cli import app

pytestmark = pytest.mark.m1

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "gate_fixtures"

M1 = "M1 not implemented"


@pytest.mark.xfail(reason=M1)
def test_init_then_ingest_produces_silver_and_quarantine(node_dir: Path) -> None:
    """`kourob init demo && kourob ingest fixtures/events.jsonl` produces silver rows and
    a quarantine file with reasons for the malformed fixtures."""
    assert runner.invoke(app, ["init", str(node_dir)]).exit_code == 0
    result = runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])
    assert result.exit_code == 0

    silver = list((node_dir / "data" / "silver").rglob("*.parquet"))
    assert silver, "ingest produced no silver rows"

    quarantine = list((node_dir / "data" / "quarantine").rglob("*"))
    quarantine = [p for p in quarantine if p.is_file() and p.name != ".gitkeep"]
    assert quarantine, "malformed fixtures produced no quarantine file"

    reasons = "\n".join(p.read_text(encoding="utf-8") for p in quarantine)
    assert "reason" in reasons, "quarantine entries must carry a reason"


@pytest.mark.xfail(reason=M1)
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


@pytest.mark.xfail(reason=M1)
def test_malformed_lines_are_rejected_at_the_parse_step() -> None:
    from kourob.gate import Gate

    gate = Gate.from_schema(FIXTURES / "schema.odcs.yaml")
    for line in (FIXTURES / "malformed.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        outcome = gate.check_raw(line)
        assert outcome.rejected
        assert outcome.gate_step == "parse", f"{line[:40]!r} rejected at {outcome.gate_step}"


@pytest.mark.xfail(reason=M1)
def test_every_mcp_answer_carries_the_full_envelope(node_dir: Path) -> None:
    """Every answer over MCP includes data, rendered, citations, receipt_id."""
    from kourob.ports.mcp import handle

    runner.invoke(app, ["init", str(node_dir)])
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])

    for tool, args in [
        ("query", {"question": "how many winners did A hit"}),
        ("get_page", {"page": "index"}),
        ("list_schemas", {}),
    ]:
        answer = handle(node_dir, tool, args)
        assert answer.data is not None
        assert answer.rendered
        assert answer.receipt_id.startswith("rcpt_")
        assert isinstance(answer.citations, list)


@pytest.mark.xfail(reason=M1)
def test_ledger_verify_passes_and_tampering_breaks_it(node_dir: Path) -> None:
    """`kourob ledger verify` passes; tampering with one receipt makes it fail."""
    from kourob.ledger.verify import tamper_for_test, verify

    runner.invoke(app, ["init", str(node_dir)])
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])
    runner.invoke(app, ["query", "how many winners", "--node", str(node_dir)])

    assert runner.invoke(app, ["ledger", "verify", "--node", str(node_dir)]).exit_code == 0
    assert verify(node_dir).ok

    tamper_for_test(node_dir, index=0, field="price_credits", value=0.0)

    assert runner.invoke(app, ["ledger", "verify", "--node", str(node_dir)]).exit_code != 0
    report = verify(node_dir)
    assert not report.ok
    assert report.first_break is not None


@pytest.mark.xfail(reason=M1)
def test_a_t0_answerable_question_never_reaches_t3(node_dir: Path) -> None:
    """Assert via the receipt's tier_used, not via timing or logs."""
    from kourob.ledger.verify import read_receipts
    from kourob.types import Tier

    runner.invoke(app, ["init", str(node_dir)])
    runner.invoke(app, ["ingest", str(FIXTURES / "events.jsonl"), "--node", str(node_dir)])

    # An exact lookup the T0 SQL view answers: it must not spend a frontier token.
    result = runner.invoke(
        app, ["query", "shot 1 of point p001 in match ao-2026-f-01", "--node", str(node_dir)]
    )
    assert result.exit_code == 0

    receipt = read_receipts(node_dir)[-1]
    assert receipt.tier_used == Tier.T0, f"answered at {receipt.tier_used}, expected T0"
