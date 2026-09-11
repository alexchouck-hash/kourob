"""The request log: the dataset the node evolves against.

Brief reference: section 3.1 step 7 — *"the request log, which is itself a dataset the
evolve loop reads."* Clustering: KNP-5 section 2.

Not in the brief's section 11 layout; recorded in docs/decisions/. It is separate from the
ledger on purpose. A receipt is **published** and therefore stores hashes, never content
(KNP-2 section 1). The request log is **local**, subject to retention (brief section 15),
and stores the question — because you cannot cluster demand you cannot read.

Every row is one request, whatever happened to it: answered, refused, referred, or fallen
through every tier. Refusals are the most informative rows in here, since they are where a
node's declared scope and its real demand disagree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from kourob import events as ev

__milestone__ = "M4"

#: Words that carry the *frame* of a question rather than its subject. These survive
#: shaping; everything else collapses to a placeholder.
FRAME_WORDS = frozenset(
    [
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "about",
        "and",
        "or",
        "not",
        "no",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "how",
        "when",
        "where",
        "why",
        "many",
        "much",
        "me",
        "my",
        "tell",
        "show",
        "give",
        "list",
        "explain",
        "compare",
        "between",
    ]
)

#: Dropped entirely. Articles change nothing about what is being asked and their presence
#: would split "who wins the open" from "who wins wimbledon".
_ARTICLES = frozenset(["a", "an", "the"])

_TOKEN = re.compile(r"[a-z0-9][a-z0-9'-]*")
_NUMERIC = re.compile(r"^\d[\d.,:-]*$")

SUBJECT = "*"
NUMBER = "#"


def question_shape(question: str, *, keep: int = 6) -> str:
    """A question reduced to its *frame*: what kind of thing is being asked.

    "what is a bridge" and "what is a cell" share a shape. "who wins wimbledon" does not.
    The subject collapses to `*` and numbers to `#`, because a cluster is about a question
    being asked repeatedly, not about which row it wanted.

    This is the opposite of keeping the content words, and getting it backwards is the
    obvious mistake: keep the subject and every topic becomes its own cluster, which is the
    same as not clustering at all.

    Discrete and explainable by construction. No embedding — requests are short and already
    typed, and an embedding would add a dependency, a failure mode, and no accuracy
    (KNP-5 section 2).
    """
    shaped: list[str] = []
    for raw in _TOKEN.findall(question.lower()):
        if raw in _ARTICLES:
            continue
        if _NUMERIC.match(raw):
            token = NUMBER
        elif raw in FRAME_WORDS:
            token = raw
        else:
            token = SUBJECT
        if shaped and token == SUBJECT and shaped[-1] == SUBJECT:
            continue  # a multi-word subject is one subject
        shaped.append(token)
    return " ".join(shaped[:keep]) if shaped else "(empty)"


def answer_shape(data: Any) -> str:
    """The shape of what came back, so two answers of different kinds do not share a cluster."""
    if data is None:
        return "none"
    if isinstance(data, dict):
        return "{" + ",".join(sorted(data)[:8]) + "}"
    if isinstance(data, list):
        inner = answer_shape(data[0]) if data else "empty"
        return f"[{inner}]"
    return type(data).__name__


@dataclass
class RequestRecord:
    """One row of `logs/requests.parquet`."""

    id: str
    ts: str
    question: str
    shape: str
    caller: str
    scope_result: str
    reason: str | None
    decided_by: str
    tier_used: str | None
    tiers_tried: list[str] = field(default_factory=list)
    determinism: str | None = None
    schemas: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    answer_shape: str = "none"
    citations: list[str] = field(default_factory=list)
    citations_n: int = 0
    latency_ms: float = 0.0
    cost_credits: float = 0.0
    price_credits: float = 0.0
    receipt_id: str = ""
    settle_key: str | None = None
    request_hash: str = ""
    response_hash: str = ""

    def as_row(self) -> dict[str, Any]:
        row = self.__dict__.copy()
        for key in ("tiers_tried", "schemas", "tools", "citations"):
            row[key] = ",".join(row[key])
        return row

    @staticmethod
    def from_row(row: dict[str, Any]) -> dict[str, Any]:
        """Undo `as_row`'s flattening. Lists are stored joined so the column stays scannable."""
        out = dict(row)
        for key in ("tiers_tried", "schemas", "tools", "citations"):
            value = out.get(key)
            out[key] = [p for p in str(value or "").split(",") if p]
        return out


def new_request_id() -> str:
    return ev.new_id(ev.REQUEST_PREFIX)


__all__ = [
    "FRAME_WORDS",
    "RequestRecord",
    "answer_shape",
    "new_request_id",
    "question_shape",
]
