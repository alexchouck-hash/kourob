"""Train the T1 student from the node's own settled answers. Never from gold.

Brief reference: section 9 (Distillation), KNP-5 section 3.2, AGENTS.md section 4.

The training set is the request log joined with outcomes: every answer that was **settled
and accepted** becomes an example. Gold is never read here - it is what the student is
checked against afterwards (`calibrate.py`), and a student that trained on its own exam
would pass it for the wrong reason. `tests/test_rails.py` enforces that this module names
no gold path; the join below is the reason it never needs to.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob.ledger.outcome import Verdict
from kourob.ledger.outcomes import read_outcomes
from kourob.request_log import RequestRecord
from kourob.tiers.t1_student import (
    DEFAULT_BAR,
    MODEL_DIR,
    MODEL_FILE,
    MODEL_VERSION_PREFIX,
    load_student,
    tokens_of,
)

__milestone__ = "M5"


def settled_examples(node: Any) -> list[dict[str, Any]]:
    """Every accepted answer, as an example: tokens, frame, cited events, decision path.

    The label is what the node's *rule path* decides for the question (`rule:<id>`,
    `t3`, `refuse`), not which tier happened to answer it. That is the class the student
    is scored on against gold, and it is the same for a lookup a rule caught and a
    paraphrase a model answered. T0-caught examples are kept: T0 runs before T1, so the
    student never answers them, but it must know they exist to place the boundary.
    """
    from kourob.loops.distill.calibrate import teacher_label

    verdicts = {o.about: o.verdict for o in read_outcomes(node.ledger)}
    if node.store.stats("requests")["rows"] == 0:
        return []
    examples: list[dict[str, Any]] = []
    for raw in node.store.scan("requests", order_by="id"):
        row = RequestRecord.from_row(raw)
        if verdicts.get(str(row.get("receipt_id") or "")) is not Verdict.ACCEPTED:
            continue
        if row.get("scope_result") != "in_scope" or not row.get("citations"):
            continue
        examples.append(
            {
                "question": row["question"],
                "shape": row.get("shape") or "",
                "tokens": sorted(tokens_of(row["question"])),
                "label": teacher_label(node, row["question"]),
                "citations": list(row.get("citations") or []),
                "settle_key": row.get("settle_key"),
                "receipt_id": row.get("receipt_id"),
            }
        )
    return examples


def train_student(node: Any) -> Path:
    """Write `tiers/t1/student.json` from the settled examples. Keeps the calibrated bar."""
    examples = settled_examples(node)
    previous = load_student(node.dir)
    revision = 1
    if previous and previous.version.startswith(MODEL_VERSION_PREFIX + "."):
        try:
            revision = int(previous.version.rsplit(".", 1)[1]) + 1
        except ValueError:
            revision = 1

    model = {
        "version": f"{MODEL_VERSION_PREFIX}.{revision}",
        "task": "answer",
        "trained_at": ev.now().isoformat(),
        "trained_on": len(examples),
        "trained_from": {
            "sources": ["requests", "outcomes"],
            "verdict": Verdict.ACCEPTED.value,
            "labels": "teacher_label: the rule path's decision, not the answering tier",
            "note": "settled answers only; gold is for calibration and is never read here",
        },
        "bar": previous.bar if previous else DEFAULT_BAR,
        "examples": examples,
    }
    path = Path(node.dir) / MODEL_DIR / MODEL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=1), encoding="utf-8")
    return path


__all__ = ["settled_examples", "train_student"]
