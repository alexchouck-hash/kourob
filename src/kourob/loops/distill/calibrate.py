"""Calibrate the student against gold, per class. Never train on it.

Brief reference: section 15 (distilled tiers copying teacher mistakes), KNP-5 section 3.2.

Gold is read through the store by logical table name, only here and only to *score*. The
student's confidence bar is set so that, on gold questions it is confident about, its label
matches at least `target` of the time - and the check is **per class**, because a student
that matches on aggregate while collapsing a rare class is the classic distillation failure
and an average hides it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from kourob.tiers.t1_student import DEFAULT_BAR, load_student, model_path

__milestone__ = "M5"

DEFAULT_TASK = "scope_classifier"
TARGET = 0.95
REFUSE = "refuse"


def gold_rows(node: Any, task: str = DEFAULT_TASK) -> list[dict[str, Any]]:
    if node.store.stats("gold")["rows"] == 0:
        return []
    return node.store.query(
        "SELECT question, label FROM gold WHERE task = $task", {"task": task}
    ).to_pylist()


def teacher_label(node: Any, question: str) -> str:
    """What the node's rule path decides for a question: the label the student imitates.

    `rule:<id>` when a T0 rule binds; `refuse` when scope refuses; `t3` when the question
    is in scope and no rule binds, which is what T3 would have been asked.
    """
    from kourob import scope as scope_mod
    from kourob.routes import RouteTable
    from kourob.tiers.t0_rules import load_rules

    decision = scope_mod.check(
        node.manifest,
        RouteTable(node.store, node.manifest.prune),
        question,
        own_did=node.did,
        hops=[],
    )
    if not decision.in_scope:
        return REFUSE
    for rule in load_rules(node.dir):
        if rule.bind(question) is not None:
            return f"rule:{rule.id}"
    return "t3"


def fallback_label(node: Any, question: str) -> str:
    """What happens when the student has no opinion: the cascade carries on without it.

    A question of a kind the student has never seen is not a refusal - refusal is scope's
    decision, not the student's. It is whatever scope and the tiers above would do: `refuse`
    if out of scope, otherwise `t3`. Scoring a silent student as if it had refused would
    punish it for knowing its limits.
    """
    from kourob import scope as scope_mod
    from kourob.routes import RouteTable

    decision = scope_mod.check(
        node.manifest,
        RouteTable(node.store, node.manifest.prune),
        question,
        own_did=node.did,
        hops=[],
    )
    return REFUSE if not decision.in_scope else "t3"


@dataclass
class Scores:
    task: str
    n: int
    teacher_accuracy: float
    student_accuracy: float
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    weakest_class: str | None = None

    @property
    def gap(self) -> float:
        return self.teacher_accuracy - self.student_accuracy


def compare_to_teacher(node: Any, task: str = DEFAULT_TASK) -> Scores:
    """Teacher and student, each scored against gold, per class."""
    rows = gold_rows(node, task)
    if not rows:
        raise ValueError(f"no gold for task {task!r}: nothing to compare against")
    student = load_student(node.dir)

    per_class: dict[str, dict[str, float]] = {}
    teacher_hits = student_hits = 0
    for row in rows:
        question, label = str(row["question"]), str(row["label"])
        bucket = per_class.setdefault(label, {"n": 0, "teacher": 0, "student": 0})
        bucket["n"] += 1
        if teacher_label(node, question) == label:
            teacher_hits += 1
            bucket["teacher"] += 1
        predicted = student.predict_label(question)[0] if student else None
        if (predicted or fallback_label(node, question)) == label:
            student_hits += 1
            bucket["student"] += 1

    for bucket in per_class.values():
        bucket["teacher_accuracy"] = bucket["teacher"] / bucket["n"]
        bucket["student_accuracy"] = bucket["student"] / bucket["n"]
    weakest = min(per_class, key=lambda c: per_class[c]["student_accuracy"]) if per_class else None
    return Scores(
        task=task,
        n=len(rows),
        teacher_accuracy=teacher_hits / len(rows),
        student_accuracy=student_hits / len(rows),
        per_class=per_class,
        weakest_class=weakest,
    )


def calibrate_bar(node: Any, *, task: str = DEFAULT_TASK, target: float = TARGET) -> float:
    """The lowest confidence bar at which the student's confident answers hit `target`.

    Walks candidate bars from low to high and keeps the first where, on every class with
    any confident prediction, accuracy among confident predictions is at least `target`.
    A class the student is never confident about is not a failure - it is work left to the
    tiers above. Written back into the model file.
    """
    student = load_student(node.dir)
    rows = gold_rows(node, task)
    if student is None or not rows:
        return DEFAULT_BAR

    scored = []
    for row in rows:
        label, score = student.predict_label(str(row["question"]))
        scored.append(
            (score, label or fallback_label(node, str(row["question"])), str(row["label"]))
        )

    chosen = 1.0
    for bar in [i / 20 for i in range(2, 21)]:
        confident = [(pred, truth) for score, pred, truth in scored if score >= bar]
        if not confident:
            continue
        per_class: dict[str, list[bool]] = {}
        for pred, truth in confident:
            per_class.setdefault(truth, []).append(pred == truth)
        if all(sum(hits) / len(hits) >= target for hits in per_class.values()):
            chosen = bar
            break

    path = model_path(node.dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["bar"] = chosen
    data["calibrated_on"] = {"task": task, "n": len(rows), "target": target}
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return chosen


__all__ = [
    "DEFAULT_TASK",
    "REFUSE",
    "TARGET",
    "Scores",
    "calibrate_bar",
    "compare_to_teacher",
    "fallback_label",
    "gold_rows",
    "teacher_label",
]
