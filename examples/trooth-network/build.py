"""Build the Trooth network: five source nodes, two desks, seven cells connected.

    uv run python examples/trooth-network/build.py

- **nws-node, open-meteo-node, usgs-node, bls-node, fred-node**: one node per Trooth feed.
  Each holds the feed's envelope (a Trooth-shaped snapshot of the real source, signed
  locally), Trooth's published scorecard for it, and its **Modafied emblem** - the
  independent benchmark's attestation, verified against Modafied's manifest before it is
  held.
- **weather-desk**: holds nothing; refers nws and open-meteo questions to the two weather
  nodes. So a weather question from the front takes two hops.
- **trooth-desk**: the front. Refers weather to weather-desk, earthquakes to usgs-node,
  the economy to bls-node and fred-node.

Ask the front anything in those domains and the receipt chain crosses up to three nodes.
Then `credits.md` is generated from what the nodes hold: every feed with its licence and
attribution, every Trooth scorecard page, every Modafied emblem with the notice - the
network advertising what it uses. `tests/test_trooth_network.py` builds all of it the same
way. Nothing generated is committed: the cells land in `cells/`, gitignored.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob.credits import credits_markdown
from kourob.ports import modafied, trooth

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
CONTRACTS = (EXAMPLES / "trooth-node" / "contracts", HERE / "contracts")
TROOTH_SCORECARDS = EXAMPLES / "trooth-node" / "fixtures" / "scorecards"
ENVELOPES = EXAMPLES / "trooth-set" / "fixtures" / "envelopes"
SET_RULES = EXAMPLES / "trooth-set" / "rules"
RULES = HERE / "rules"
MODAFIED = HERE / "fixtures" / "modafied"
CATALOG = HERE / "fixtures" / "trooth-catalog"
DEFAULT_ROOT = HERE / "cells"

#: Source nodes: id -> (scope summary, rule directories to install, entities).
SOURCES: dict[str, tuple[str, tuple[Path, ...], tuple[str, ...]]] = {
    "nws": (
        "nws weather observations at KJFK from the national weather service: temperature, "
        "humidity, wind, conditions; the trooth scorecard and modafied emblem of nws",
        (SET_RULES / "weather",),
        ("weather-station",),
    ),
    "open-meteo": (
        "open-meteo model weather at KJFK: temperature, humidity, wind; the trooth "
        "scorecard and modafied emblem of open-meteo",
        (SET_RULES / "weather",),
        ("weather-grid",),
    ),
    "usgs-earthquake": (
        "earthquakes from the usgs past-hour feed: largest quake, magnitude, count; the "
        "trooth scorecard and modafied emblem of usgs-earthquake",
        (SET_RULES / "seismic",),
        ("earthquake",),
    ),
    "bls": (
        "the consumer price index (cpi, inflation) from bls; the trooth scorecard and "
        "modafied emblem of bls",
        (SET_RULES / "economy",),
        ("price-index",),
    ),
    "fred": (
        "fred economic series from the st louis fed; the trooth scorecard and modafied "
        "emblem of fred (no envelope yet: fred needs an api key)",
        (SET_RULES / "economy",),
        ("economic-series",),
    ),
}

NODE_NAME = {sid: f"{sid}-node" for sid in SOURCES} | {"usgs-earthquake": "usgs-node"}

WEATHER_DESK_EXCLUDES = {
    "nws": r"\bnws\b|national weather|station|conditions",
    "open-meteo": r"open-meteo|model|grid",
}
FRONT_EXCLUDES = {
    "weather-desk": r"weather|temperature|humidity|wind|observation|kjfk|nws|open-meteo",
    "usgs-node": r"earthquake|quake|seismic|magnitude|usgs",
    "bls-node": r"cpi|inflation|price index|consumer price|bls",
    "fred-node": r"fred|st louis|economic series",
}


def _fresh_cell(cell: Path, name: str, scope: str) -> Path:
    node_mod.init(cell, name=name, scope=scope)
    for stale in ("note.odcs.yaml", "note_check.odcs.yaml"):
        (cell / "schemas" / stale).unlink(missing_ok=True)
    (cell / "tiers" / "t0" / "rules" / "note-lookup.yaml").unlink(missing_ok=True)
    shutil.rmtree(cell / "fixtures", ignore_errors=True)
    return cell


def _source_node(root: Path, source_id: str) -> tuple[node_mod.Node, list[str]]:
    scope, rule_dirs, entities = SOURCES[source_id]
    cell = _fresh_cell(root / NODE_NAME[source_id], NODE_NAME[source_id], scope)
    for contracts in CONTRACTS:
        for contract in sorted(contracts.glob("*.odcs.yaml")):
            shutil.copy2(contract, cell / "schemas" / contract.name)
    for rules in (*rule_dirs, RULES):
        for rule in sorted(rules.glob("*.yaml")):
            shutil.copy2(rule, cell / "tiers" / "t0" / "rules" / rule.name)

    node = node_mod.open_node(cell)
    node.manifest.scope.schemas = ["observation.v1", "scorecard.v1", "emblem.v1", "node_change.v1"]
    node.manifest.scope.entities = list(entities)
    manifest_mod.save(cell, node.manifest)

    node = node_mod.open_node(cell)
    lines: list[str] = []
    envelope = ENVELOPES / f"{source_id}.json"
    if envelope.exists():
        lines += trooth.tree_to_events(envelope)
    lines += trooth.tree_to_events(TROOTH_SCORECARDS / f"{source_id}.json")
    manifest = MODAFIED / "manifest.json"
    attestation = MODAFIED / f"{source_id}.json"
    refused: list[str] = []
    if attestation.exists():
        import json

        try:
            lines += modafied.attestation_to_events(
                json.loads(attestation.read_text(encoding="utf-8")),
                json.loads(manifest.read_text(encoding="utf-8")),
            )
        except modafied.UnverifiedError as why:
            refused.append(str(why))
    report = node.gate.ingest_lines(lines, source="trooth-network fixtures")
    assert report.rejected == 0, report.reasons
    return node_mod.open_node(cell), refused


def _desk(root: Path, name: str, scope: str, excludes: dict[str, str], dids: dict[str, str]):
    cell = _fresh_cell(root / name, name, scope)
    node = node_mod.open_node(cell)
    node.manifest.scope.excludes = [
        manifest_mod.Exclusion(pattern=pattern, refer_to=dids[target])
        for target, pattern in excludes.items()
    ]
    node.manifest.bridge.bridge_limit = 1
    manifest_mod.save(cell, node.manifest)
    for target in excludes:
        node_mod.connect(node_mod.open_node(cell), root / target)
    return node_mod.open_node(cell)


def attribution() -> dict[str, str]:
    """Each feed's attribution text, from Trooth's catalog entries (fixtures)."""
    out: dict[str, str] = {}
    for path in sorted(CATALOG.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        lic = entry.get("license") or {}
        out[entry["id"]] = f"{entry['name']}: {lic.get('attribution_text') or entry['name']}"
    return out


def build(root: Path | str = DEFAULT_ROOT) -> tuple[dict[str, node_mod.Node], list[str]]:
    """Init seven cells, connect the desks, write credits.md. Returns (nodes, refusals)."""
    root = Path(root)
    nodes: dict[str, node_mod.Node] = {}
    refused: list[str] = []
    for source_id in SOURCES:
        node, why = _source_node(root, source_id)
        nodes[NODE_NAME[source_id]] = node
        refused += why

    dids = {name: n.did for name, n in nodes.items()}
    weather = _desk(
        root,
        "weather-desk",
        "a desk for weather at KJFK: refers to nws-node (station) and open-meteo-node (model)",
        {NODE_NAME[s]: p for s, p in WEATHER_DESK_EXCLUDES.items()},
        dids,
    )
    nodes["weather-desk"] = weather
    dids["weather-desk"] = weather.did
    nodes["trooth-desk"] = _desk(
        root,
        "trooth-desk",
        "the front desk of a network of trooth-fed nodes: holds nothing, refers weather, "
        "earthquakes and the economy to the nodes that do",
        FRONT_EXCLUDES,
        dids,
    )
    (root / "credits.md").write_text(
        credits_markdown(nodes.values(), attribution=attribution(), title="trooth-network credits"),
        encoding="utf-8",
    )
    return nodes, refused


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if args.root.exists():
        shutil.rmtree(args.root)  # an example is rebuilt, not upgraded
    nodes, refused = build(args.root)
    for name, node in nodes.items():
        print(f"{name:<16} {node.did}  events {node.store.stats('silver')['rows']}")
    for why in refused:
        print(f"refused emblem: {why}")
    front = args.root / "trooth-desk"
    print(f"\ncredits:        {args.root / 'credits.md'}")
    print(f"ask the front:  uv run kourob query 'nws observation at KJFK' --node {front}")
    print(
        f"watch the net:  uv run streamlit run examples/trooth-network/dashboard.py -- {args.root}"
    )


if __name__ == "__main__":
    main()
