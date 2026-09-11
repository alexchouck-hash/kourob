"""T1: the distilled student, trained on this node's own settled answers.

Brief reference: sections 3.3, 15. KNP-5 section 3.2.

A node without a gold set cannot enable T1. Enforced, not conventional: `enable` refuses,
and the cascade will not construct the tier without a model file that `enable` wrote.

What the student is, at this scale: a nearest-settled-answer model. Every settled, accepted
answer the node has given becomes an example - the question's content tokens, the events it
cited, the decision path that produced it. A new question is matched to its nearest example
by token overlap within the same question frame, and answered from that example's events.
No weights, no torch: a few thousand examples in a JSON file, deterministic, explainable,
and three orders of magnitude cheaper than the frontier call it replaces. It is `attested`,
not `derived` - it says what the node said before, not what the events entail.

Its confidence is calibrated against gold (`loops/distill/calibrate.py`); the training data
never is (`loops/distill/train.py`). That separation is the whole defence against a student
that learns the teacher's mistakes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kourob.request_log import question_shape
from kourob.store import Store
from kourob.tiers.base import Request, TierHandler, TierResult
from kourob.types import Tier

__milestone__ = "M5"

MODEL_DIR = "tiers/t1"
MODEL_FILE = "student.json"
MODEL_VERSION_PREFIX = "student-s@0.1"
DEFAULT_BAR = 0.6
#: A student answer costs a JSON scan. Measured, not priced.
T1_COMPUTE_COST = 0.00002

#: One character is a token. "shot 1" and "shot 2" differ by exactly one character, and a
#: tokenizer that drops it makes every lookup on a point look like the same question.
_TOKEN = re.compile(r"[a-z0-9][a-z0-9-]*")


def tokens_of(question: str) -> set[str]:
    return set(_TOKEN.findall(question.lower()))


def similarity(a: set[str], b: set[str]) -> float:
    """Jaccard over content tokens. Symmetric, bounded, and easy to explain in a receipt."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class Student:
    """The model file, loaded."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.version: str = data["version"]
        self.bar: float = float(data.get("bar", DEFAULT_BAR))
        self.examples: list[dict[str, Any]] = data.get("examples", [])
        self.trained_on: int = int(data.get("trained_on", len(self.examples)))
        self.trained_from: dict[str, Any] = data.get("trained_from", {})

    def nearest(self, question: str) -> tuple[dict[str, Any] | None, float]:
        shape = question_shape(question)
        asked = tokens_of(question)
        best, best_score = None, 0.0
        for example in self.examples:
            if example.get("shape") != shape:
                continue  # a different kind of question, however many words it shares
            score = similarity(asked, set(example.get("tokens", [])))
            if score > best_score:
                best, best_score = example, score
        return best, best_score

    def predict_label(self, question: str) -> tuple[str | None, float]:
        example, score = self.nearest(question)
        return (example.get("label") if example else None), score


def model_path(node_dir: Path | str) -> Path:
    return Path(node_dir) / MODEL_DIR / MODEL_FILE


def load_student(node_dir: Path | str) -> Student | None:
    path = model_path(node_dir)
    if not path.exists():
        return None
    return Student(json.loads(path.read_text(encoding="utf-8")))


class T1Student(TierHandler):
    """Answer from the nearest settled example, or decline."""

    tier = Tier.T1

    def __init__(self, node_dir: Path | str, store: Store) -> None:
        self.node_dir = Path(node_dir)
        self.store = store
        self.student = load_student(node_dir)

    def available(self) -> bool:
        return self.student is not None and bool(self.student.examples)

    def attempt(self, request: Request) -> TierResult:
        if self.student is None:
            return TierResult.miss(Tier.T1, "no student trained")
        example, score = self.student.nearest(request.question)
        if example is None or not example.get("citations"):
            return TierResult.miss(Tier.T1, "no settled example of this kind of question")
        if score < self.student.bar:
            return TierResult.miss(
                Tier.T1, f"nearest example at {score:.2f}, bar {self.student.bar:.2f}"
            )

        events = [row for cite in example["citations"] if (row := self.store.get("silver", cite))]
        if not events:
            return TierResult.miss(Tier.T1, "the example's events are no longer in silver")

        rendered = "\n".join(f"{_claim(e.get('payload') or {})} [{e['id']}]" for e in events)
        return TierResult(
            tier=Tier.T1,
            answered=True,
            confidence=score,
            data={
                "nearest": example.get("question"),
                "similarity": score,
                "events": [e["id"] for e in events],
            },
            rendered=rendered,
            citations=[e["id"] for e in events],
            model_version=self.student.version,
            cost_credits=T1_COMPUTE_COST,
            detail=f"nearest settled example at {score:.2f}",
            settle_key=example.get("settle_key"),
        )

    # ---------------------------------------------------------------------- lifecycle

    @staticmethod
    def enable(node: Any) -> Path:
        """Train, write the model, and switch T1 on. Refuses without gold.

        The gold check is here and nowhere softer. A student trained on the teacher's own
        answers and never checked against anything else learns the teacher's mistakes, and
        brief section 15 names that as the failure this tier must not have.
        """
        from kourob import manifest as manifest_mod
        from kourob.loops.distill.calibrate import calibrate_bar, gold_rows
        from kourob.loops.distill.train import train_student

        if not gold_rows(node):
            raise ValueError(
                "T1 needs a gold set before it can be enabled: this node has none. Push labelled "
                "examples with `kourob distill gold <file>` (a gold row is a question and a "
                "label), then enable. A student nobody can check learns the teacher's mistakes."
            )
        path = train_student(node)
        calibrate_bar(node)
        node.manifest.tiers.setdefault("t1", manifest_mod.TierConfig()).enabled = True
        node.manifest.tiers["t1"].model = MODEL_VERSION_PREFIX
        manifest_mod.save(node.dir, node.manifest)
        return path

    @staticmethod
    def disable(node: Any) -> bool:
        """Switch T1 off. The model file stays, so enabling again is a lookup."""
        from kourob import manifest as manifest_mod

        cfg = node.manifest.tiers.get("t1")
        if cfg is None or not cfg.enabled:
            return False
        cfg.enabled = False
        manifest_mod.save(node.dir, node.manifest)
        return True


def _claim(payload: dict[str, Any]) -> str:
    strings = {k: v for k, v in payload.items() if isinstance(v, str)}
    if not strings:
        return json.dumps(payload, sort_keys=True)
    return strings[max(strings, key=lambda k: len(strings[k]))]


__all__ = [
    "DEFAULT_BAR",
    "MODEL_DIR",
    "MODEL_FILE",
    "MODEL_VERSION_PREFIX",
    "T1_COMPUTE_COST",
    "Student",
    "T1Student",
    "load_student",
    "model_path",
    "similarity",
    "tokens_of",
]
