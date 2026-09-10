"""`kourob ledger verify`, `kourob trace`, and the tamper helper the M1 test needs.

Brief reference: sections 4.2 and 4.3. KNP-2 sections 3 and 4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kourob import identity, manifest
from kourob.ledger.chain import Ledger, VerifyReport
from kourob.ledger.receipt import Receipt
from kourob.store.parquet_duckdb import ParquetDuckDBStore

__milestone__ = "M1"


def _ledger(node_dir: Path | str) -> Ledger:
    node_dir = Path(node_dir)
    m = manifest.load(node_dir)
    did = m.identity.did or identity.load_did(node_dir)
    return Ledger(node_dir, ParquetDuckDBStore(node_dir, partition_by=m.store.partition_by), did)


def verify(node_dir: Path | str) -> VerifyReport:
    return _ledger(node_dir).verify()


def read_receipts(node_dir: Path | str) -> list[Receipt]:
    """Receipts only, oldest first, typed. Outcomes share the chain but are another record.

    Typed rather than raw dicts because a caller reasoning about `tier_used` or
    `determinism` should be reasoning about the enum, not about whatever string happened to
    be written.
    """
    return [
        Receipt.model_validate(record)
        for record in _ledger(node_dir).records()
        if record.get("kind", "receipt") == "receipt"
    ]


@dataclass
class Chain:
    """What `kourob trace` renders: the nodes, receipts and events behind one answer."""

    receipts: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"chain for {self.receipts[0]['id']}" if self.receipts else "empty chain"]
        for r in self.receipts:
            lines.append(
                f"  {r['id']}  node={r.get('node', '?')[:24]}...  tier={r.get('tier_used')}  "
                f"determinism={r.get('determinism')}  price={r.get('price_credits')}"
            )
            for cite in r.get("citations") or []:
                lines.append(f"      cites {cite}")
            for o in self.outcomes:
                if o.get("about") == r["id"]:
                    note = f" - {o['note']}" if o.get("note") else ""
                    lines.append(f"      {o['verdict']} by {o['source']} ({o['id']}){note}")
        for e in self.events:
            prov = e.get("provenance") or {}
            lines.append(f"  {e['id']}  {e.get('schema_ref')}  from {prov.get('source', '?')}")
        return "\n".join(lines)


def trace(node_dir: Path | str, receipt_id: str) -> Chain:
    """Walk one receipt to its events, its sources, and any upstream receipts."""
    ledger = _ledger(node_dir)
    by_id = {r["id"]: r for r in ledger.records()}
    chain = Chain()
    frontier = [receipt_id]
    seen: set[str] = set()
    while frontier:
        rid = frontier.pop(0)
        record = by_id.get(rid)
        if record is None or rid in seen:
            continue
        seen.add(rid)
        chain.receipts.append(record)
        if record.get("node") and record["node"] not in chain.nodes:
            chain.nodes.append(record["node"])
        frontier.extend(record.get("upstream") or [])
    receipt_ids = {r["id"] for r in chain.receipts}
    chain.outcomes = [
        record
        for record in by_id.values()
        if record.get("kind") == "outcome" and record.get("about") in receipt_ids
    ]
    cited = {c for r in chain.receipts for c in (r.get("citations") or [])}
    if cited:
        for event_id in sorted(cited):
            event = ledger.store.get("silver", event_id)
            if event:
                chain.events.append(event)
    return chain


def tamper_for_test(node_dir: Path | str, *, index: int, field: str, value: Any) -> None:
    """Edit one record in place so a test can prove the chain notices.

    Only ever called from tests. It exists in the package rather than in a test helper
    because "can you detect tampering" is a property of the ledger, and the thing that
    performs the tampering should live next to the thing that claims to catch it.
    """
    node_dir = Path(node_dir)
    ledger = _ledger(node_dir)
    records = ledger.records()
    if not records:
        raise ValueError("nothing to tamper with: the ledger is empty")
    records[index][field] = value

    receipts_dir = node_dir / "ledger" / "receipts"
    for part in receipts_dir.glob("*/*.parquet"):
        part.unlink()
    rows = []
    for record in records:
        row = dict(record)
        for col in ("citations", "upstream", "hops", "evidence"):
            if isinstance(row.get(col), list):
                row[col] = json.dumps(row[col])
        rows.append(row)
    ledger.store.append("receipts", rows)


__all__ = ["Chain", "read_receipts", "tamper_for_test", "trace", "verify"]
