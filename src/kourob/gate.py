"""The write path: stamp, parse, validate, dedupe, classify, threshold, route.

Brief reference: section 3.1 step 3.

The ONLY module permitted to write the silver and gold tables. It reaches them through the
Store by logical table name, never by path (ADR-0001). CI enforces both halves.

Everything that fails lands in quarantine **with the step that rejected it**, because
repeated quarantine reasons become schema and rule proposals in the next evolve
(brief section 6.3). A gate that only says "no" throws away the most useful signal a node
produces about its own scope.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob.schema.loader import Contract, load, load_dir
from kourob.store import Store

__milestone__ = "M1"

#: Steps in order. A push is rejected by the first one that objects.
STEPS = ("stamp", "parse", "validate", "dedupe", "classify", "threshold", "route")

#: Prefix the fixtures use to annotate expectations. Stripped before anything sees a push.
_ANNOTATION_PREFIX = "_"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
#: A phone number, not a timestamp. Requires an international prefix, a grouping space or
#: paren, or a long unbroken run of digits — the three things a date never has. Without
#: this, every ISO 8601 field in the corpus reads as a phone number.
_PHONE = re.compile(r"(?:\+\d[\d\s().-]{7,}\d|\d[\d().-]*[\s(][\d\s().-]{6,}\d|\d{10,})")

#: Fields that carry a consent basis, so PII in them is declared rather than smuggled.
_CONSENT_FIELDS = ("consent", "consent_basis")


@dataclass(frozen=True)
class GateOutcome:
    """What the gate decided, and which step decided it."""

    rejected: bool
    gate_step: str = "route"
    reason: str = ""
    event: ev.Event | None = None
    pii: bool = False

    @property
    def accepted(self) -> bool:
        return not self.rejected


@dataclass
class IngestReport:
    """The result of one ingest run. `kourob ingest` prints this."""

    accepted: int = 0
    rejected: int = 0
    reasons: dict[str, int] = field(default_factory=dict)
    event_ids: list[str] = field(default_factory=list)

    def record(self, outcome: GateOutcome) -> None:
        if outcome.rejected:
            self.rejected += 1
            self.reasons[outcome.gate_step] = self.reasons.get(outcome.gate_step, 0) + 1
        else:
            self.accepted += 1
            if outcome.event:
                self.event_ids.append(outcome.event.id)


class Gate:
    """One gate per node, holding the contracts that node owns."""

    def __init__(
        self,
        contracts: dict[str, Contract],
        *,
        store: Store | None = None,
        now: datetime | None = None,
    ) -> None:
        self.contracts = contracts
        self.store = store
        self._now = now
        self._seen_content: set[str] = set()
        self._seen_keys: dict[str, str] = {}
        if store is not None:
            self._load_seen()

    @classmethod
    def from_schema(cls, path: Path | str, **kw: Any) -> Gate:
        contract = load(path)
        return cls({contract.id: contract}, **kw)

    @classmethod
    def for_node(cls, node_dir: Path | str, *, store: Store | None = None) -> Gate:
        return cls(load_dir(Path(node_dir) / "schemas"), store=store)

    def _load_seen(self) -> None:
        """Dedupe must survive a restart, or a second ingest of a file duplicates it.

        A node with no events yet has no columns to select, so ask `stats` first rather
        than letting a binder error stand in for "nothing here yet".
        """
        if self.store is None or self.store.stats("silver")["rows"] == 0:
            return
        rows = self.store.query("SELECT content_hash, dedupe_key FROM silver").to_pylist()
        for row in rows:
            if row.get("content_hash"):
                self._seen_content.add(row["content_hash"])
            if row.get("dedupe_key"):
                self._seen_keys[row["dedupe_key"]] = row["content_hash"]

    def check_raw(self, line: str) -> GateOutcome:
        """Step 2, parse. A line that is not JSON never reaches a schema."""
        try:
            push = json.loads(line)
        except json.JSONDecodeError as exc:
            return GateOutcome(True, "parse", f"not valid JSON: {exc.msg}")
        if not isinstance(push, dict):
            return GateOutcome(True, "parse", f"top level is {type(push).__name__}, want object")
        return self.check(push)

    def check(self, push: dict[str, Any]) -> GateOutcome:
        """Steps 1 and 3 to 7. Returns the first objection, with the step that raised it."""
        body = {k: v for k, v in push.items() if not k.startswith(_ANNOTATION_PREFIX)}

        schema_ref = body.pop("schema_ref", None)
        if not schema_ref:
            return GateOutcome(True, "stamp.no_schema_ref", "nothing says what shape this is")
        contract = self.contracts.get(schema_ref)
        if contract is None:
            return GateOutcome(
                True, "stamp.unknown_schema", f"this node does not own {schema_ref!r}"
            )

        if not body:
            return GateOutcome(True, "validate.empty", "schema_ref and nothing else")
        violations = contract.validate(body)
        if violations:
            return GateOutcome(True, violations[0].step, "; ".join(str(v) for v in violations))
        if "no_future_timestamps" in contract.quality:
            problem = self._future_timestamp(contract, body)
            if problem:
                return GateOutcome(True, "validate.future_timestamp", problem)

        content_hash = ev.sha256({"schema_ref": schema_ref, **body})
        key_fields = contract.key_fields or self._infer_key_fields(contract)
        key = ev.dedupe_key(schema_ref, body, key_fields) if key_fields else content_hash
        if content_hash in self._seen_content:
            return GateOutcome(True, "dedupe.exact", "byte-identical to a fact already held")
        if key in self._seen_keys and self._seen_keys[key] != content_hash:
            return GateOutcome(
                True,
                "dedupe.key",
                f"same {list(key_fields)} as a fact already held, different content: a "
                "contradiction, not a new fact",
            )

        pii_field = self._find_pii(contract, body)
        if pii_field and not any(body.get(c) for c in _CONSENT_FIELDS):
            return GateOutcome(
                True, "classify.pii", f"{pii_field!r} carries personal data with no consent basis"
            )

        # threshold: novelty has nothing to do at event grain. See the fixtures README.

        self._seen_content.add(content_hash)
        self._seen_keys[key] = content_hash
        stamp = self._now or ev.now()
        return GateOutcome(
            False,
            "route",
            "",
            ev.Event(
                id=ev.new_id(),
                schema_ref=schema_ref,
                ts=self._event_ts(contract, body),
                ingested_at=stamp,
                payload=body,
                provenance=ev.Provenance(
                    source="push", activity="gate", agent="local", retrieved_at=stamp
                ),
                pii=bool(pii_field),
            ),
            pii=bool(pii_field),
        )

    # ---------------------------------------------------------------------- helpers

    @staticmethod
    def _infer_key_fields(contract: Contract) -> tuple[str, ...]:
        """Without a declared key, the required non-timestamp fields identify the fact."""
        return tuple(f.name for f in contract.fields if f.required and f.logical_type != "date")[:3]

    def _event_ts(self, contract: Contract, body: dict[str, Any]) -> datetime:
        """When the fact became true, which is not when the node heard about it."""
        for spec in contract.fields:
            if spec.logical_type == "date" and isinstance(body.get(spec.name), str):
                parsed = self._parse_ts(body[spec.name])
                if parsed:
                    return parsed
        return self._now or ev.now()

    @staticmethod
    def _parse_ts(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _future_timestamp(self, contract: Contract, body: dict[str, Any]) -> str | None:
        horizon = self._now or ev.now()
        for spec in contract.fields:
            if spec.logical_type != "date" or not isinstance(body.get(spec.name), str):
                continue
            parsed = self._parse_ts(body[spec.name])
            if parsed and parsed > horizon:
                return f"{spec.name} {body[spec.name]} is later than ingestion time"
        return None

    @staticmethod
    def _is_free_text(contract: Contract, name: str) -> bool:
        """Only free text is scanned for PII.

        A field the contract constrains — a date, an enum, a pattern — is structured, and
        structured fields are where the personal data is *declared*. Scanning them produces
        false positives that swamp the real ones: an ISO 8601 timestamp reads as a phone
        number to any regex loose enough to catch phone numbers.

        The dangerous field is the undeclared one somebody added because there was nowhere
        else to put a note.
        """
        spec = contract.field_by_name(name)
        if spec is None:
            return True
        return spec.logical_type == "string" and spec.enum is None and spec.pattern is None

    @classmethod
    def _find_pii(cls, contract: Contract, body: dict[str, Any]) -> str | None:
        for name, value in body.items():
            if not isinstance(value, str) or not cls._is_free_text(contract, name):
                continue
            if _EMAIL.search(value) or _PHONE.search(value):
                return name
        return None

    # ------------------------------------------------------------------------ ingest

    def ingest_lines(self, lines: list[str], *, source: str = "push") -> IngestReport:
        """Run the gate over raw lines and write both sides. The only writer of silver."""
        report = IngestReport()
        accepted: list[dict[str, Any]] = []
        quarantined: list[dict[str, Any]] = []
        stamp = (self._now or ev.now()).isoformat()

        for line in lines:
            if not line.strip():
                continue
            outcome = self.check_raw(line)
            report.record(outcome)
            if outcome.rejected:
                quarantined.append(
                    {
                        "id": ev.new_id("qtn_"),
                        "raw": line[:4000],
                        "reason": outcome.reason,
                        "gate_step": outcome.gate_step,
                        "ingested_at": stamp,
                        "source": source,
                    }
                )
            elif outcome.event is not None:
                accepted.append(self._silver_row(outcome.event))

        if self.store is not None:
            if accepted:
                self.store.append("silver", accepted)
            if quarantined:
                self.store.append("quarantine", quarantined)
        return report

    def ingest_gold(self, lines: list[str], *, task: str, source: str = "gold") -> IngestReport:
        """Write labelled examples to gold. The gate is the only writer of gold, too.

        A gold row is `{"question": ..., "label": ...}` for a task. It is not an event —
        nothing in the world happened — so it does not pass the contract steps; it passes
        parse and a shape check, and it is deduped on (task, question). Training code
        never reads this table; calibration does (AGENTS.md section 4).
        """
        report = IngestReport()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        if self.store is not None and self.store.stats("gold")["rows"]:
            for row in self.store.query(
                "SELECT question FROM gold WHERE task = $task", {"task": task}
            ).to_pylist():
                seen.add(str(row["question"]).strip().lower())

        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                report.record(GateOutcome(True, "parse", f"not valid JSON: {exc.msg}"))
                continue
            question = str(raw.get("question") or "").strip()
            label = raw.get("label")
            if not question or label is None:
                report.record(
                    GateOutcome(True, "validate.missing_required", "gold needs question and label")
                )
                continue
            key = question.lower()
            if key in seen:
                report.record(GateOutcome(True, "dedupe.exact", "already in gold"))
                continue
            seen.add(key)
            report.accepted += 1
            rows.append(
                {
                    "id": ev.new_id("gold_"),
                    "task": task,
                    "question": question,
                    "label": str(label),
                    "source": source,
                    "ts": (self._now or ev.now()).isoformat(),
                }
            )
        if self.store is not None and rows:
            self.store.append("gold", rows)
        return report

    def _silver_row(self, event: ev.Event) -> dict[str, Any]:
        contract = self.contracts[event.schema_ref]
        key_fields = contract.key_fields or self._infer_key_fields(contract)
        return {
            "id": event.id,
            "schema_ref": event.schema_ref,
            "ts": event.ts.isoformat(),
            "ingested_at": event.ingested_at.isoformat(),
            "payload": event.payload,
            "provenance": event.provenance.model_dump(mode="json"),
            "content_hash": ev.sha256({"schema_ref": event.schema_ref, **event.payload}),
            "dedupe_key": (
                ev.dedupe_key(event.schema_ref, event.payload, key_fields) if key_fields else None
            ),
            "pii": event.pii,
        }

    def ingest_file(self, path: Path | str) -> IngestReport:
        text = Path(path).read_text(encoding="utf-8")
        return self.ingest_lines(text.splitlines(), source=str(path))


__all__ = ["STEPS", "Gate", "GateOutcome", "IngestReport"]
