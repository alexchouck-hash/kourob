"""Submitting, settling and reading outcomes.

Brief reference: KNP-2 section 6, ADR-0007.

A receipt records what a node did. An outcome records whether it held up. Without the
second, the request log is unlabelled and the evolve loop can make a node cheaper but not
better — which is the failure mode that kills the design.

Nothing here ever edits a receipt. A wrong answer stays in the chain with a correction
pointing at what was true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from kourob import events as ev
from kourob.ledger.chain import RECORD_OUTCOME, Ledger
from kourob.ledger.outcome import Outcome, OutcomeSource, Verdict
from kourob.schema.loader import Contract

__milestone__ = "M4"

_DURATION = re.compile(r"^(\d+)\s*([smhdw])$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def parse_window(text: str | None) -> timedelta | None:
    """`7d`, `30d`, `12h`. Returns None for an undeclared window, which means never settles."""
    if not text:
        return None
    match = _DURATION.match(text.strip())
    if not match:
        raise ValueError(f"not a duration: {text!r}. Use forms like 7d, 12h, 30m.")
    return timedelta(**{_UNITS[match.group(2)]: int(match.group(1))})


def settle_key(schema_ref: str, subject: dict[str, Any]) -> str:
    """The identity of what an answer was *about*, hashed.

    Hashed rather than stored in the clear because a receipt may be published and the
    subject may not be publishable. Two parties computing it from the same fields agree
    without either learning the other's data.
    """
    return ev.sha256({"schema_ref": schema_ref, "subject": subject})


class OutcomeError(ValueError):
    """A submission that cannot be recorded, as opposed to one that is merely unwelcome."""


@dataclass
class Settlement:
    """What one ingested event settled."""

    event_id: str
    outcomes: list[str]


def submit(
    ledger: Ledger,
    receipt_id: str,
    *,
    verdict: Verdict,
    source: OutcomeSource = OutcomeSource.CALLER,
    evidence: list[str] | None = None,
    by: str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Outcome:
    """Append an outcome judging one receipt.

    The submitter is checked against the receipt's caller. A mismatch is **not** rejected:
    a third party noticing an error is useful even when it cannot be trusted. It is recorded
    at `source: caller`, which carries the lowest weight (ADR-0007).
    """
    records = {r["id"]: r for r in ledger.records()}
    receipt = records.get(receipt_id)
    if receipt is None:
        raise OutcomeError(f"no receipt {receipt_id} in this ledger")
    if receipt.get("kind", "receipt") != "receipt":
        raise OutcomeError(f"{receipt_id} is an outcome, not a receipt: outcomes are not judged")

    evidence = list(evidence or [])
    if verdict is Verdict.CORRECTED and not evidence:
        raise OutcomeError(
            "a correction must point at what was true: pass the event id that says so. "
            "Saying an answer was wrong without saying what was right teaches nothing."
        )

    if by is not None and by != receipt.get("caller") and source is not OutcomeSource.REALITY:
        source = OutcomeSource.CALLER

    stamp = now or ev.now()
    answered_at = _parse_ts(receipt.get("ts"))
    record = ledger.append(
        RECORD_OUTCOME,
        {
            "id": ev.new_id(ev.OUTCOME_PREFIX),
            "about": receipt_id,
            "verdict": verdict.value,
            "source": source.value,
            "evidence": evidence,
            "by": by,
            "note": note,
            "latency_s": (stamp - answered_at).total_seconds() if answered_at else None,
            "ts": stamp.isoformat(),
        },
    )
    return Outcome.model_validate(record)


def read_outcomes(ledger: Ledger) -> list[Outcome]:
    return [Outcome.model_validate(r) for r in ledger.records() if r.get("kind") == RECORD_OUTCOME]


def outcomes_for(ledger: Ledger, receipt_id: str) -> list[Outcome]:
    return [o for o in read_outcomes(ledger) if o.about == receipt_id]


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


# ----------------------------------------------------------------------------- settling


def settle_from_event(
    ledger: Ledger,
    contracts: dict[str, Contract],
    event: dict[str, Any],
    *,
    now: datetime | None = None,
) -> Settlement:
    """Append `source: reality` outcomes for every receipt this event settles.

    This is the only outcome source that is free, honest and unarguable: nobody's opinion,
    just a later fact arriving (ADR-0007). A node whose answers are eventually settled by
    data it was going to ingest anyway has a self-labelling training set, and that is worth
    designing for.
    """
    payload = event.get("payload") or {}
    settled: list[str] = []

    for contract in contracts.values():
        if not contract.settles or contract.settles_against != event.get("schema_ref"):
            continue
        if any(field not in payload for field in contract.settle_key):
            continue

        verdict = _verdict_from(contract, payload)
        if verdict is None:
            # The schema says answers are settleable but not how to judge them. Recording
            # a verdict here would be inventing one; leave the receipts unresolved, which
            # is itself information (KNP-3 section 3).
            continue

        key = settle_key(contract.id, {f: payload[f] for f in contract.settle_key})
        for receipt in ledger.records():
            if receipt.get("kind", "receipt") != "receipt" or receipt.get("settle_key") != key:
                continue
            if outcomes_for(ledger, receipt["id"]):
                continue  # already settled; a fact arriving twice is not two outcomes
            outcome = submit(
                ledger,
                receipt["id"],
                verdict=verdict,
                source=OutcomeSource.REALITY,
                evidence=[event["id"]],
                note=f"settled by {event['schema_ref']} {event['id']}",
                now=now,
            )
            settled.append(outcome.id)

    return Settlement(event_id=str(event.get("id", "?")), outcomes=settled)


def _verdict_from(contract: Contract, payload: dict[str, Any]) -> Verdict | None:
    if contract.settle_verdict_field:
        raw = payload.get(contract.settle_verdict_field)
        if isinstance(raw, str):
            try:
                return Verdict(raw)
            except ValueError:
                return None
    if contract.settle_default:
        try:
            return Verdict(contract.settle_default)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------- reporting


@dataclass
class SettlementStatus:
    """How much of what this node said has been checked, and how much held up.

    `unresolved` is **computed, never written**. Appending a record to say that nothing
    happened would manufacture evidence out of its own absence, and the chain is for facts.
    """

    total: int = 0
    settled: int = 0
    accepted: int = 0
    corrected: int = 0
    rejected: int = 0
    unresolved: int = 0
    pending: int = 0

    @property
    def settle_rate(self) -> float:
        return self.settled / self.total if self.total else 0.0

    @property
    def accept_rate(self) -> float | None:
        """None when nothing has settled: an unmeasured node is not a perfect one."""
        return self.accepted / self.settled if self.settled else None

    def quality_multiplier(self, q_min: float = 0.5, q_max: float = 1.5) -> float:
        """KNP-3 section 3. Unresolved counts against the denominator, so a node nobody
        checks drifts toward `q_min` rather than keeping a premium it has not earned."""
        denominator = self.accepted + self.corrected + self.rejected + self.unresolved
        if denominator == 0:
            return q_min
        return max(q_min, min(q_max, self.accepted / denominator))


def settlement_status(
    ledger: Ledger,
    contracts: dict[str, Contract],
    *,
    now: datetime | None = None,
) -> SettlementStatus:
    """Count receipts by whether they settled, and how."""
    stamp = now or ev.now()
    windows = {c.id: parse_window(c.outcome_window) for c in contracts.values() if c.outcome_window}
    default_window = next(iter(windows.values()), None)

    by_receipt: dict[str, list[Outcome]] = {}
    receipts: list[dict[str, Any]] = []
    for record in ledger.records():
        if record.get("kind", "receipt") == "receipt":
            receipts.append(record)
        else:
            by_receipt.setdefault(str(record.get("about")), []).append(
                Outcome.model_validate(record)
            )

    status = SettlementStatus(total=len(receipts))
    for receipt in receipts:
        outcomes = by_receipt.get(receipt["id"], [])
        if outcomes:
            status.settled += 1
            verdict = outcomes[-1].verdict
            if verdict is Verdict.ACCEPTED:
                status.accepted += 1
            elif verdict is Verdict.CORRECTED:
                status.corrected += 1
            elif verdict is Verdict.REJECTED:
                status.rejected += 1
            continue
        answered_at = _parse_ts(receipt.get("ts"))
        if default_window and answered_at and stamp - answered_at > default_window:
            status.unresolved += 1
        else:
            status.pending += 1
    return status


__all__ = [
    "OutcomeError",
    "Settlement",
    "SettlementStatus",
    "outcomes_for",
    "parse_window",
    "read_outcomes",
    "settle_from_event",
    "settle_key",
    "settlement_status",
    "submit",
]
