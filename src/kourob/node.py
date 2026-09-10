"""Opening a cell: the handle every port and command starts from.

Brief reference: section 8. Cell definition: KNP-8.

Not in the brief's section 11 layout. It exists because `init`, `ingest`, `query`, `doctor`,
the MCP port and the REST port were each about to assemble the same four objects — manifest,
store, gate, ledger — in the same order, and four copies of that is where drift starts.
Recorded in docs/decisions/.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kourob import identity, manifest
from kourob.gate import Gate
from kourob.ledger.chain import Ledger
from kourob.schema.loader import Contract, load_dir
from kourob.store.parquet_duckdb import ParquetDuckDBStore

__milestone__ = "M1"

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template"

#: Directories `kourob init` creates that git will not carry, because a node's local state
#: is gitignored inside the template itself (KNP-8: the membrane includes the key material).
_RUNTIME_DIRS = (".kourob/gen", ".kourob/cache", ".kourob/keys", "logs", "ledger/receipts")


@dataclass
class Node:
    """One cell, opened."""

    dir: Path
    manifest: manifest.Manifest
    store: ParquetDuckDBStore
    did: str

    @property
    def contracts(self) -> dict[str, Contract]:
        return load_dir(self.dir / "schemas")

    @property
    def gate(self) -> Gate:
        return Gate(self.contracts, store=self.store)

    @property
    def ledger(self) -> Ledger:
        return Ledger(self.dir, self.store, self.did)

    def ingest(self, path: Path | str) -> tuple[Any, list[Any]]:
        """Push a file through the gate, then let the new facts settle old answers.

        Settlement lives here rather than in the gate because the gate writes silver and
        settlement writes the ledger, and the module that does both is the assembly point,
        not either half. Returns the ingest report and whatever it settled.
        """
        from kourob.ledger.outcomes import settle_from_event

        report = self.gate.ingest_file(path)
        if not report.event_ids:
            return report, []

        ledger, contracts = self.ledger, self.contracts
        if not any(c.settles for c in contracts.values()):
            return report, []

        settlements = []
        for event_id in report.event_ids:
            event = self.store.get("silver", event_id)
            if event is None:
                continue
            settled = settle_from_event(ledger, contracts, event)
            if settled.outcomes:
                settlements.append(settled)
        return report, settlements

    def health(self) -> list[tuple[str, bool, str]]:
        """What `kourob doctor` reports: (check, ok, detail)."""
        checks: list[tuple[str, bool, str]] = [
            (
                "manifest",
                True,
                f"{self.manifest.identity.name} ({self.manifest.scope.summary[:48]})",
            ),
            ("identity", self.did.startswith("did:key:z"), self.did),
        ]
        contracts = self.contracts
        checks.append(
            (
                "schemas",
                len(contracts) <= self.manifest.cell.max_schemas,
                f"{len(contracts)} of {self.manifest.cell.max_schemas} allowed: "
                f"{', '.join(sorted(contracts)) or 'none'}",
            )
        )
        try:
            rows = self.store.stats("silver")["rows"]
            checks.append(("store", True, f"{rows} events in silver"))
        except Exception as exc:
            checks.append(("store", False, str(exc)))
        report = self.ledger.verify()
        checks.append(("ledger", report.ok, str(report)))

        from kourob.ledger.outcomes import settlement_status

        status = settlement_status(self.ledger, contracts)
        settleable = any(c.settles for c in contracts.values())
        checks.append(
            (
                "outcomes",
                settleable or status.total == 0,
                f"{status.settled}/{status.total} settled, {status.unresolved} unresolved, "
                f"quality {status.quality_multiplier():.2f}"
                + ("" if settleable else "  (no contract declares settles_against)"),
            )
        )
        return checks


def open_node(node_dir: Path | str) -> Node:
    node_dir = Path(node_dir)
    m = manifest.load(node_dir)
    did = m.identity.did if m.identity.did.startswith("did:key:") else identity.load_did(node_dir)
    return Node(
        dir=node_dir,
        manifest=m,
        store=ParquetDuckDBStore(node_dir, partition_by=m.store.partition_by),
        did=did,
    )


def init(target: Path | str, *, name: str | None = None, scope: str = "") -> Node:
    """Lay a cell down from the template, generate its key, and fill its identity.

    Refuses an existing node. Re-running `init` over a live cell would orphan its ledger,
    which is the one mistake in this codebase that cannot be undone.
    """
    target = Path(target)
    if (target / manifest.MANIFEST_FILE).exists():
        raise FileExistsError(f"{target} is already a node. `kourob init` will not overwrite one.")
    target.mkdir(parents=True, exist_ok=True)

    for item in TEMPLATE_DIR.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
    for runtime in _RUNTIME_DIRS:
        (target / runtime).mkdir(parents=True, exist_ok=True)

    did = identity.generate(target)
    node_name = name or target.resolve().name
    raw = (target / manifest.MANIFEST_FILE).read_text(encoding="utf-8")
    for placeholder, value in (
        ("{{ node_did }}", did),
        ("{{ node_name }}", node_name),
        ("{{ set_name }}", "default"),
        ("{{ scope_summary }}", scope or f"undeclared. Write GOAL.md before {node_name} serves."),
    ):
        raw = raw.replace(placeholder, value)
    (target / manifest.MANIFEST_FILE).write_text(raw, encoding="utf-8")
    return open_node(target)


def connect(node: Node, target: Path | str, *, source: str = "connect") -> Any:
    """Make a neighbour of a node on disk. One command, one row, never an import.

    KNP-9 section 1: fetch the neighbour's identity and declared scope, write a route, and
    emit nothing else. No config file, no generated stub, no restart. Disconnecting is
    `RouteTable.forget`, and the receipts either side wrote stay verifiable forever.
    """
    from kourob.routes import Route, RouteTable, keywords_of

    other = open_node(target)
    if other.did == node.did:
        raise ValueError("a cell cannot connect to itself")
    route = Route(
        node=other.did,
        endpoint=str(Path(target).resolve()),
        name=other.manifest.identity.name,
        summary=other.manifest.scope.summary,
        schemas=list(other.manifest.scope.schemas),
        keywords=keywords_of(other.manifest.scope.summary),
        source=source,
    )
    RouteTable(node.store, node.manifest.prune).save(route)
    return route


def cell_size(node: Node) -> dict[str, Any]:
    """Measure a cell against its ceiling (KNP-8 section 2.3).

    Over budget is not a warning to be tuned away: the cell sheds or divides.
    """
    budget = node.manifest.cell
    sources = [p for p in node.dir.rglob("*.py") if ".kourob" not in p.parts]
    lines = sum(len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) for p in sources)
    hot_bytes = (
        sum(p.stat().st_size for p in (node.dir / "data" / "silver").rglob("*.parquet"))
        if (node.dir / "data" / "silver").exists()
        else 0
    )
    measured = {
        "source_files": (len(sources), budget.max_source_files),
        "source_lines": (lines, budget.max_source_lines),
        "schemas": (len(node.contracts), budget.max_schemas),
        "tiers": (sum(1 for t in node.manifest.tiers.values() if t.enabled), budget.max_tiers),
        "hot_storage_mb": (round(hot_bytes / 1_000_000, 2), budget.max_hot_storage_mb),
        "tools": (len(list((node.dir / "tools").glob("*.yaml"))), budget.max_tools),
    }
    over = [k for k, (value, limit) in measured.items() if value > limit]
    return {"measured": measured, "over": over, "on_exceed": budget.on_exceed}


__all__ = ["Node", "cell_size", "connect", "init", "open_node"]
