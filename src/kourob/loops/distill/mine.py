"""Rule mining: turn a cluster that has always been a function into a T0 rule, by replay.

Brief reference: KNP-5 section 3.3. Decided in ADR-0008.

The frontier model's job was to *discover* the function. Once a cluster's answers have
always been determined by (question, cited events), running them through a model is pure
waste — and the cost curve in GOAL.md comes almost entirely from noticing that.

A mined rule is the same artefact a hand-written one is: a regex over the question and a
SQL query over silver, run by the same T0 tier. Mining does not write it by hand; it reads
the shape out of the cluster and then **replays the candidate over every settled request
in the cluster**. Exact match on every one, or no promotion. Partial coverage is allowed —
a rule may decline requests — but partial correctness is not.

What "exact" means here, precisely: for each settled request the candidate, bound to that
request's question, must return **exactly the event ids the settled answer cited**. That is
what `derived` promises a stranger — the same events — and it is checkable from the request
log today. Replaying the rendered text as well needs the log to keep it; that is a follow-up,
and until then a mined rule renders a field of the event rather than a model's prose.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from kourob.loops.evolve import MIN_COVERAGE, ClusterStats
from kourob.request_log import FRAME_WORDS, RequestRecord
from kourob.store import Store
from kourob.tiers.t0_rules import RULES_DIR, Rule

__milestone__ = "M5"

_TOKEN = re.compile(r"[a-z0-9][a-z0-9'-]*")
_ARTICLES = frozenset(["a", "an", "the"])


@dataclass
class Candidate:
    """A mined rule and the evidence for it. `promotable` is the ADR-0008 gate."""

    rule_id: str
    schema_ref: str
    bind_field: str
    render_field: str
    match: str
    sql: str
    render: str
    replayed: int = 0
    exact: int = 0
    covered: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def replay_exact_match(self) -> float:
        """Of the requests the rule answered, the share it answered with exactly the settled
        events. This must be 1.0 — 99% right is not a function (ADR-0008)."""
        return self.exact / self.covered if self.covered else 0.0

    @property
    def coverage(self) -> float:
        """Of the settled requests, the share the rule answered at all. May be below 1.0."""
        return self.covered / self.replayed if self.replayed else 0.0

    @property
    def promotable(self) -> bool:
        return (
            self.replayed > 0 and self.replay_exact_match == 1.0 and self.coverage >= MIN_COVERAGE
        )

    def as_yaml(self) -> str:
        body = {
            "id": self.rule_id,
            "description": (
                f"Mined from a cluster of {self.replayed} settled requests over "
                f"{self.schema_ref}; exact on every one it covers (ADR-0008)."
            ),
            "match": self.match,
            "confidence": 1.0,
            "sql": self.sql,
            "render": self.render,
            "mined": {
                "replayed": self.replayed,
                "exact": self.exact,
                "covered": self.covered,
                "coverage": round(self.coverage, 4),
            },
            "settles": {"schema": self.schema_ref, "key": [self.bind_field]},
        }
        return yaml.safe_dump(body, sort_keys=False, width=100)

    def write(self, node_dir: Path | str) -> Path:
        """Install the rule. Only `tend` should call this, and only within autonomy (KNP-7)."""
        path = Path(node_dir) / RULES_DIR / f"{self.rule_id}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.as_yaml(), encoding="utf-8")
        return path


def subject_of(question: str) -> str:
    """The part of a question that is not its frame: what it is *about*.

    The inverse of `question_shape`. "what is a bridge" -> "bridge"; "tell me about the
    pruning loop" -> "pruning loop". Frame words and articles are dropped; whatever is left,
    in order, is the subject.
    """
    words = [
        w for w in _TOKEN.findall(question.lower()) if w not in FRAME_WORDS and w not in _ARTICLES
    ]
    return " ".join(words)


def _settled_rows(
    store: Store, cluster: ClusterStats, verdicts: dict[str, Any]
) -> list[dict[str, Any]]:
    from kourob.loops.clustering import cluster_key

    if store.stats("requests")["rows"] == 0:
        return []
    rows = []
    for raw in store.scan("requests", order_by="id"):
        record = RequestRecord.from_row(raw)
        if cluster_key(record) != cluster.key:
            continue
        if str(record.get("receipt_id") or "") not in verdicts:
            continue
        rows.append(record)
    return rows


def _find_binding(store: Store, rows: list[dict[str, Any]]) -> tuple[str, str, str] | None:
    """Which payload field the question's subject equals, on every settled request.

    A rule needs one field to bind on. Mining does not guess it: it takes the field the
    subject equals on the most rows, and requires that field to be the match on **every row
    where the subject equals any field at all**. Rows whose subject equals nothing are the
    ones the rule will decline — they are not evidence against the binding, they are the
    uncovered tail that coverage counts. A row whose subject equals a *different* field is
    evidence against it, and disqualifies the binding outright.

    Whatever this chooses is still replayed. The replay gate, not this search, is what
    keeps a coincidence out of T0.
    """
    per_field: Counter[tuple[str, str]] = Counter()
    render_fields: Counter[tuple[str, str]] = Counter()
    bound_rows = 0
    for record in rows:
        cited = record.get("citations") or []
        if len(cited) != 1:
            return None  # v1 mines single-event lookups only; multi-event joins are a follow-up
        event = store.get("silver", cited[0])
        if event is None:
            return None
        payload = event.get("payload") or {}
        subject = subject_of(record["question"])
        matched_any = False
        for name, value in payload.items():
            if isinstance(value, str) and value.lower() == subject:
                per_field[(str(event["schema_ref"]), name)] += 1
                matched_any = True
        bound_rows += matched_any
        for name, value in payload.items():
            if isinstance(value, str) and len(value) > 20:
                render_fields[(str(event["schema_ref"]), name)] += 1

    if not per_field:
        return None
    (schema_ref, bind_field), hits = per_field.most_common(1)[0]
    if hits != bound_rows:
        return None  # some subject names a *different* field: not one function
    render_field = next(
        (name for (s, name), _ in render_fields.most_common() if s == schema_ref), bind_field
    )
    return schema_ref, bind_field, render_field


def _match_pattern(rows: list[dict[str, Any]]) -> str:
    """A regex that binds the subject from questions shaped like the cluster's dominant frame.

    Built from a frame actually seen, not invented. One frame, not every frame: Python's
    `re` forbids the same group name twice in a pattern, so a rule that bound `subject`
    from several frames at once would need a list of patterns, and `Rule` has one. Questions
    in the other frames go uncovered, which the replay gate counts honestly against
    coverage rather than papering over. Multi-frame rules are a follow-up.

    The first `*` in the frame is the subject; any later `*` is matched and discarded.
    """
    frames = Counter(str(r.get("shape") or "") for r in rows if r.get("shape"))
    if not frames:
        return r"(?P<subject>.+)"
    frame, _ = frames.most_common(1)[0]
    parts: list[str] = []
    bound = False
    for token in frame.split():
        if token == "*":
            parts.append(
                r"(?P<subject>[a-z0-9][a-z0-9 '-]*?)" if not bound else r"[a-z0-9][a-z0-9 '-]*?"
            )
            bound = True
        elif token == "#":
            parts.append(r"\d[\d.,:-]*")
        else:
            parts.append(re.escape(token))
    return r"\b" + r"\s+(?:(?:a|an|the)\s+)?".join(parts) + r"\s*\??$"


def mine_rule(
    store: Store,
    cluster: ClusterStats,
    verdicts: dict[str, Any],
    *,
    rule_id: str | None = None,
) -> Candidate | None:
    """Mine one cluster. Returns None when there is nothing to mine — which is the common
    case and not a failure: most clusters are not functions of one event."""
    if not cluster.is_function or not cluster.can_promote:
        return None
    rows = _settled_rows(store, cluster, verdicts)
    if not rows:
        return None
    binding = _find_binding(store, rows)
    if binding is None:
        return None
    schema_ref, bind_field, render_field = binding

    candidate = Candidate(
        rule_id=rule_id or f"mined-{schema_ref.split('.')[0]}-{bind_field}",
        schema_ref=schema_ref,
        bind_field=bind_field,
        render_field=render_field,
        match=_match_pattern(rows),
        sql=(
            "SELECT id, json_extract_string(payload, '$."
            + render_field
            + "') AS "
            + render_field
            + ", json_extract_string(payload, '$."
            + bind_field
            + "') AS "
            + bind_field
            + "\nFROM silver\nWHERE schema_ref = '"
            + schema_ref
            + "'\n"
            "  AND lower(json_extract_string(payload, '$." + bind_field + "')) = lower($subject)\n"
            "ORDER BY ts"
        ),
        render="{" + render_field + "}",
    )
    replay(store, candidate, rows)
    return candidate


def replay(store: Store, candidate: Candidate, rows: list[dict[str, Any]]) -> Candidate:
    """Run the candidate over every settled request and compare cited event sets.

    Every one, not a sample: the failure cases for a mined rule are systematic — one join,
    one edge case — and a sample is exactly the wrong estimator for them (ADR-0008 option B).
    """
    rule = Rule.from_dict({"id": candidate.rule_id, "match": candidate.match, "sql": candidate.sql})
    candidate.replayed = len(rows)
    for record in rows:
        params = rule.bind(record["question"])
        if params is None:
            continue  # declined: allowed, counts against coverage only
        got = {r["id"] for r in store.query(rule.sql, params).to_pylist() if r.get("id")}
        if not got:
            continue
        candidate.covered += 1
        want = set(record.get("citations") or [])
        if got == want:
            candidate.exact += 1
        else:
            candidate.misses.append(str(record.get("receipt_id") or "?"))
    return candidate


__all__ = ["Candidate", "mine_rule", "replay", "subject_of"]
