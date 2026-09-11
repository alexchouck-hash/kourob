"""The per-node hash chain: append, walk, verify.

Brief reference: section 4.2. KNP-2 sections 2 and 3.

One append-only chain per node carries both receipts and outcomes (ADR-0007). Each record's
`prev` is the sha256 of its predecessor's canonical signed form; the genesis record's `prev`
is the hash of the node's own `did:key`, so a chain cannot be silently re-parented onto
another node's history.

What this catches: an operator editing history after the fact. What it does not catch: a
compromised node signing false records going forward. That needs the transparency log in
KNP-4 section 4, and saying so plainly is better than implying tamper-proofing we do not
have.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob import identity
from kourob.ledger.outcome import SIGNED_FIELDS as OUTCOME_FIELDS
from kourob.ledger.receipt import SIGNED_FIELDS as RECEIPT_FIELDS
from kourob.store import Store

__milestone__ = "M1"

RECORD_RECEIPT = "receipt"
RECORD_OUTCOME = "outcome"

#: Both record kinds share one table, so a row read back carries null columns belonging to
#: the other kind. That is storage, not content: `signed_view` is what a record *is*, and it
#: is what the signature covers.


def genesis_prev(did: str) -> str:
    """The anchor. Binding it to the did stops a chain being re-parented."""
    return "sha256:" + hashlib.sha256(did.encode("utf-8")).hexdigest()


def signed_view(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Exactly the fields covered by the signature, in a canonical shape."""
    return {name: record.get(name) for name in fields}


def record_hash(record: dict[str, Any], fields: tuple[str, ...]) -> str:
    return ev.sha256(signed_view(record, fields))


def fields_for(kind: str) -> tuple[str, ...]:
    return RECEIPT_FIELDS if kind == RECORD_RECEIPT else OUTCOME_FIELDS


@dataclass
class Break:
    """Where a chain stopped being trustworthy, and why."""

    index: int
    record_id: str
    problem: str

    def __str__(self) -> str:
        return f"record {self.index} ({self.record_id}): {self.problem}"


@dataclass
class VerifyReport:
    ok: bool
    checked: int
    first_break: Break | None = None
    receipts: int = 0
    outcomes: int = 0

    def __str__(self) -> str:
        if self.ok:
            return (
                f"ledger ok: {self.checked} records "
                f"({self.receipts} receipts, {self.outcomes} outcomes)"
            )
        return f"ledger BROKEN at {self.first_break}"


class Ledger:
    """Append and verify one node's chain."""

    def __init__(self, node_dir: Path | str, store: Store, did: str) -> None:
        self.node_dir = Path(node_dir)
        self.store = store
        self.did = did

    # ---------------------------------------------------------------------- reading

    def records(self) -> list[dict[str, Any]]:
        """Every record, oldest first, by explicit sequence.

        **Not** by id. Ids are `<prefix>_<ULID>`, and `outc_` sorts before `rcpt_`, so id
        order interleaves the chain wrongly the moment a node records its first outcome.
        `seq` is written on append and is unambiguous. It is not signed, because it does not
        need to be: reordering the chain breaks `prev`, and `prev` is the integrity
        mechanism. `seq` only says how to read it.
        """
        if self.store.stats("receipts")["rows"] == 0:
            return []
        return self.store.scan("receipts", order_by="seq")

    def head(self) -> dict[str, Any] | None:
        records = self.records()
        return records[-1] if records else None

    def next_prev(self) -> str:
        head = self.head()
        return record_hash(head, fields_for(head["kind"])) if head else genesis_prev(self.did)

    # ---------------------------------------------------------------------- writing

    def append(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        """Sign `body` into the chain and return the stored record.

        A node that cannot write a record must fail the request rather than answer without
        one (KNP-0 I1). That is why this raises rather than returning a status.
        """
        fields = fields_for(kind)
        existing = self.records()
        prev = (
            record_hash(existing[-1], fields_for(existing[-1]["kind"]))
            if existing
            else genesis_prev(self.did)
        )
        record = {
            **body,
            "kind": kind,
            "node": self.did,
            "seq": len(existing),
            "prev": prev,
        }
        private_key = identity.load_private_key(self.node_dir)
        record["sig"] = identity.sign(private_key, signed_view(record, fields))
        self.store.append("receipts", [record])
        return record

    def extend(self, entries: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """Append many records in one pass, chaining them to each other.

        `append` re-reads the chain to find its predecessor, which is fine for one record
        and quadratic for a thousand. This reads once and links the batch internally, so a
        node settling a hundred answers from one arriving fact — or a fixture simulating a
        month of traffic — costs one scan rather than a hundred.

        The result is the same chain: each record still carries the hash of the one before
        it, and `verify` cannot tell how they were written.
        """
        if not entries:
            return []
        existing = self.records()
        prev = (
            record_hash(existing[-1], fields_for(existing[-1]["kind"]))
            if existing
            else genesis_prev(self.did)
        )
        seq = len(existing)
        private_key = identity.load_private_key(self.node_dir)

        written: list[dict[str, Any]] = []
        for kind, body in entries:
            fields = fields_for(kind)
            record = {**body, "kind": kind, "node": self.did, "seq": seq, "prev": prev}
            record["sig"] = identity.sign(private_key, signed_view(record, fields))
            written.append(record)
            prev = record_hash(record, fields)
            seq += 1

        self.store.append("receipts", written)
        return written

    # --------------------------------------------------------------------- verifying

    def verify(self) -> VerifyReport:
        """Walk the chain, checking every signature and every `prev`.

        Reports the **first** break only: everything after a break is unverifiable, and
        listing all of them is noise dressed as thoroughness.
        """
        expected_prev = genesis_prev(self.did)
        receipts = outcomes = 0
        for index, record in enumerate(self.records()):
            kind = record.get("kind", RECORD_RECEIPT)
            fields = fields_for(kind)
            rid = str(record.get("id", "?"))

            if record.get("prev") != expected_prev:
                return VerifyReport(
                    False,
                    index,
                    Break(index, rid, "prev does not match its predecessor"),
                    receipts,
                    outcomes,
                )
            signature = record.get("sig")
            if not signature or not identity.verify(
                self.did, signed_view(record, fields), str(signature)
            ):
                return VerifyReport(
                    False, index, Break(index, rid, "signature does not verify"), receipts, outcomes
                )

            if kind == RECORD_RECEIPT:
                receipts += 1
            else:
                outcomes += 1
            expected_prev = record_hash(record, fields)

        return VerifyReport(True, receipts + outcomes, None, receipts, outcomes)


__all__ = [
    "RECORD_OUTCOME",
    "RECORD_RECEIPT",
    "Break",
    "Ledger",
    "VerifyReport",
    "genesis_prev",
    "record_hash",
    "signed_view",
]
