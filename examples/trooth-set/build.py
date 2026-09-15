"""Build the Trooth set: three data nodes, one front node, connected.

    uv run python examples/trooth-set/build.py

- **weather-node** holds NWS and Open-Meteo observations for KJFK, and their scorecards.
- **seismic-node** holds the USGS past-hour earthquake feed, and its scorecard.
- **economy-node** holds the BLS CPI reading, and its scorecard.
- **trooth-desk** holds nothing. It declares three exclusions that refer to the nodes above,
  and a route to each. Ask it anything in their domains and it bridges once, hands back the
  direct route, and refers after that (KNP-1 sections 4 and 5).

All four are built from `kourob init` plus the contracts in `../trooth-node/contracts` and
the rules in `rules/`. The envelopes in `fixtures/envelopes/` are Trooth-shaped snapshots
of the real public sources, signed locally (see `fixtures/make_envelopes.py`); the
scorecards are the ones Trooth published. `tests/test_trooth_set.py` calls `build` the same
way. Nothing generated is committed: the cells land in `cells/`, gitignored.
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob.ports.trooth import tree_to_events

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE.parent / "trooth-node" / "contracts"
SCORECARDS = HERE.parent / "trooth-node" / "fixtures" / "scorecards"
ENVELOPES = HERE / "fixtures" / "envelopes"
RULES = HERE / "rules"
DEFAULT_ROOT = HERE / "cells"


@dataclass(frozen=True)
class Spec:
    name: str
    scope: str
    rules: str
    sources: tuple[str, ...]
    entities: tuple[str, ...]


NODES = (
    Spec(
        "weather-node",
        "weather observations at KJFK from nws and open-meteo: temperature, humidity, wind, "
        "conditions, and the trooth scorecards of those two sources",
        "weather",
        ("nws", "open-meteo"),
        ("weather-station",),
    ),
    Spec(
        "seismic-node",
        "earthquakes: the usgs past-hour feed, largest quake, magnitude, count, and the "
        "trooth scorecard of usgs-earthquake",
        "seismic",
        ("usgs-earthquake",),
        ("earthquake",),
    ),
    Spec(
        "economy-node",
        "the consumer price index (cpi, inflation) from bls, and the trooth scorecards of "
        "bls and fred",
        "economy",
        ("bls", "fred"),
        ("price-index",),
    ),
)

#: What the desk refers where. Patterns are matched against the question (manifest Exclusion).
DESK_EXCLUDES = {
    "seismic-node": r"earthquake|quake|seismic|magnitude|usgs",
    "weather-node": r"weather|temperature|humidity|wind|observation|kjfk|nws|open-meteo",
    "economy-node": r"cpi|inflation|price index|consumer price|bls|fred",
}


def _data_node(root: Path, spec: Spec) -> node_mod.Node:
    cell = root / spec.name
    node_mod.init(cell, name=spec.name, scope=spec.scope)
    for stale in ("note.odcs.yaml", "note_check.odcs.yaml"):
        (cell / "schemas" / stale).unlink(missing_ok=True)
    (cell / "tiers" / "t0" / "rules" / "note-lookup.yaml").unlink(missing_ok=True)
    shutil.rmtree(cell / "fixtures", ignore_errors=True)
    for contract in sorted(CONTRACTS.glob("*.odcs.yaml")):
        shutil.copy2(contract, cell / "schemas" / contract.name)
    for rule in sorted((RULES / spec.rules).glob("*.yaml")):
        shutil.copy2(rule, cell / "tiers" / "t0" / "rules" / rule.name)

    node = node_mod.open_node(cell)
    node.manifest.scope.schemas = ["observation.v1", "scorecard.v1", "node_change.v1"]
    node.manifest.scope.entities = list(spec.entities)
    manifest_mod.save(cell, node.manifest)

    node = node_mod.open_node(cell)
    lines = []
    for source in spec.sources:
        envelope = ENVELOPES / f"{source}.json"
        if envelope.exists():
            lines += tree_to_events(envelope)
        card = SCORECARDS / f"{source}.json"
        if card.exists():
            lines += tree_to_events(card)
    report = node.gate.ingest_lines(lines, source="trooth-set fixtures")
    assert report.rejected == 0, report.reasons
    return node_mod.open_node(cell)


def build(root: Path | str = DEFAULT_ROOT, *, bridge_limit: int = 1) -> dict[str, node_mod.Node]:
    """Init the four cells, connect the desk to the three, return them by name."""
    root = Path(root)
    nodes = {spec.name: _data_node(root, spec) for spec in NODES}

    desk_dir = root / "trooth-desk"
    node_mod.init(
        desk_dir,
        name="trooth-desk",
        scope="a front desk for trooth-fed nodes: it holds nothing and refers weather, "
        "seismic and economy questions to the node that does",
    )
    desk = node_mod.open_node(desk_dir)
    desk.manifest.scope.excludes = [
        manifest_mod.Exclusion(pattern=pattern, refer_to=nodes[name].did)
        for name, pattern in DESK_EXCLUDES.items()
    ]
    desk.manifest.bridge.bridge_limit = bridge_limit
    manifest_mod.save(desk_dir, desk.manifest)
    for spec in NODES:
        node_mod.connect(node_mod.open_node(desk_dir), root / spec.name)
    nodes["trooth-desk"] = node_mod.open_node(desk_dir)
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if args.root.exists():
        shutil.rmtree(args.root)  # an example is rebuilt, not upgraded
    nodes = build(args.root)
    for name, node in nodes.items():
        held = node.store.stats("silver")["rows"]
        print(f"{name:<14} {node.did}  events {held}")
    desk = args.root / "trooth-desk"
    print(
        f"\nask the desk:  uv run kourob query 'largest earthquake in the last hour' --node {desk}"
    )
    print(f"watch the set: uv run streamlit run examples/trooth-set/dashboard.py -- {args.root}")


if __name__ == "__main__":
    main()
