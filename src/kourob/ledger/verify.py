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
    """What `kourob trace` renders: the nodes, receipts, outcomes and events behind one
    answer — across every node the answer passed through."""

    receipts: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"chain for {self.receipts[0]['id']}" if self.receipts else "empty chain"]
        for r in self.receipts:
            lines.append(
                f"  {r['id']}  node={r.get('node', '?')[:24]}...  scope={r.get('scope_result')}  "
                f"tier={r.get('tier_used')}  determinism={r.get('determinism')}  "
                f"price={r.get('price_credits')}"
            )
            for up in r.get("upstream") or []:
                lines.append(f"      upstream {up}")
            for cite in r.get("citations") or []:
                lines.append(f"      cites {cite}")
            for o in self.outcomes:
                if o.get("about") == r["id"]:
                    note = f" - {o['note']}" if o.get("note") else ""
                    lines.append(f"      {o['verdict']} by {o['source']} ({o['id']}){note}")
        for e in self.events:
            prov = e.get("provenance") or {}
            lines.append(f"  {e['id']}  {e.get('schema_ref')}  from {prov.get('source', '?')}")
        for up in self.unreachable:
            lines.append(f"  {up}  (upstream receipt in a ledger this node cannot reach)")
        return "\n".join(lines)


def _reachable_ledgers(node_dir: Path) -> dict[str, Path]:
    """Every ledger a trace may need: this node's, and each neighbour's on disk.

    A bridged answer's upstream receipt lives in the *neighbour's* ledger, in its own chain,
    signed with its own key. Following it means opening that ledger, which the route table
    knows how to find. A remote neighbour (HTTP) is reported as unreachable rather than
    guessed at.
    """
    from kourob.routes import RouteTable

    ledgers: dict[str, Path] = {}
    try:
        node_did = identity.load_did(node_dir)
    except FileNotFoundError:
        node_did = manifest.load(node_dir).identity.did
    ledgers[node_did] = node_dir
    m = manifest.load(node_dir)
    store = ParquetDuckDBStore(node_dir, partition_by=m.store.partition_by)
    for route in RouteTable(store, m.prune).all():
        endpoint = Path(route.endpoint) if route.endpoint else None
        if endpoint and endpoint.exists() and (endpoint / manifest.MANIFEST_FILE).exists():
            ledgers[route.node] = endpoint
    return ledgers


def trace(node_dir: Path | str, receipt_id: str) -> Chain:
    """Walk one receipt to its events, its sources, and any upstream receipts — following a
    bridge into the neighbour's ledger where the route table can reach it."""
    node_dir = Path(node_dir)
    ledgers = _reachable_ledgers(node_dir)
    loaded: dict[str, Ledger] = {}
    by_id: dict[str, tuple[dict[str, Any], str]] = {}

    def load(did: str) -> None:
        if did in loaded or did not in ledgers:
            return
        ledger = _ledger(ledgers[did])
        loaded[did] = ledger
        for record in ledger.records():
            by_id.setdefault(record["id"], (record, did))

    for did in ledgers:
        load(did)

    chain = Chain()
    frontier = [receipt_id]
    seen: set[str] = set()
    while frontier:
        rid = frontier.pop(0)
        if rid in seen:
            continue
        seen.add(rid)
        found = by_id.get(rid)
        if found is None:
            chain.unreachable.append(rid)
            continue
        record, did = found
        chain.receipts.append(record)
        if did not in chain.nodes:
            chain.nodes.append(did)
        frontier.extend(record.get("upstream") or [])

    receipt_ids = {r["id"] for r in chain.receipts}
    chain.outcomes = [
        record
        for record, _ in by_id.values()
        if record.get("kind") == "outcome" and record.get("about") in receipt_ids
    ]

    for r in chain.receipts:
        owner = loaded.get(r.get("node", ""))
        for cite in r.get("citations") or []:
            store = owner.store if owner else loaded[next(iter(loaded))].store
            event = store.get("silver", cite)
            if event and event["id"] not in {e["id"] for e in chain.events}:
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
