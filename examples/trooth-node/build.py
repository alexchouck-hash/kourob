"""Build the Trooth-fed example node from what is committed here.

    uv run python examples/trooth-node/build.py            # from the fixtures
    uv run python examples/trooth-node/build.py --live     # plus today's public scorecards

Lays a cell down with `kourob init`, swaps the starter contract for `observation.v1` and
`scorecard.v1`, installs the two T0 rules, and pushes the fixtures (one NWS envelope from
Trooth's schema examples and the five scorecards Trooth published) through the gate.
`tests/test_trooth_node.py` calls `build` the same way, so the example and the test cannot
drift apart.

Nothing generated is committed: the cell lands in `examples/trooth-node/cell/`, which is
gitignored (keys are secret, Parquet is binary, pages are derived).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob.ports.trooth import PUBLIC_SITE, events_from, tree_to_events

HERE = Path(__file__).resolve().parent
CONTRACTS = HERE / "contracts"
RULES = HERE / "rules"
FIXTURES = HERE / "fixtures"
DEFAULT_CELL = HERE / "cell"
SCOPE = "Trooth-delivered observations and the public scorecards of Trooth's sources"


def build(cell: Path | str = DEFAULT_CELL, *, live: bool = False, site: str = PUBLIC_SITE):
    """Init, install contracts and rules, ingest. Returns the opened node."""
    cell = Path(cell)
    node_mod.init(cell, name="trooth-node", scope=SCOPE)

    # The starter contract and rule are an example, not a foundation (template/schemas).
    for stale in ("note.odcs.yaml", "note_check.odcs.yaml"):
        (cell / "schemas" / stale).unlink(missing_ok=True)
    (cell / "tiers" / "t0" / "rules" / "note-lookup.yaml").unlink(missing_ok=True)
    shutil.rmtree(cell / "fixtures", ignore_errors=True)
    for contract in sorted(CONTRACTS.glob("*.odcs.yaml")):
        shutil.copy2(contract, cell / "schemas" / contract.name)
    for rule in sorted(RULES.glob("*.yaml")):
        shutil.copy2(rule, cell / "tiers" / "t0" / "rules" / rule.name)

    node = node_mod.open_node(cell)
    node.manifest.scope.schemas = ["observation.v1", "scorecard.v1", "node_change.v1"]
    node.manifest.scope.entities = ["trooth-source", "weather-station"]
    manifest_mod.save(cell, node.manifest)

    node = node_mod.open_node(cell)
    lines = tree_to_events(FIXTURES)
    if live:
        lines += events_from(site)
    report = node.gate.ingest_lines(lines, source="trooth" if live else str(FIXTURES))
    return node, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cell", type=Path, default=DEFAULT_CELL)
    parser.add_argument("--live", action="store_true", help="also pull today's scorecards")
    parser.add_argument("--site", default=PUBLIC_SITE)
    args = parser.parse_args()
    if (args.cell / manifest_mod.MANIFEST_FILE).exists():
        shutil.rmtree(args.cell)  # an example is rebuilt, not upgraded
    node, report = build(args.cell, live=args.live, site=args.site)
    print(f"{node.manifest.identity.name}  {node.did}")
    print(f"accepted {report.accepted}   quarantined {report.rejected}")
    for step, count in sorted(report.reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4}  {step}")
    print(f"\nask it:      uv run kourob query 'latest observation at KJFK' --node {args.cell}")
    print(f"watch it:    uv run streamlit run examples/trooth-node/dashboard.py -- {args.cell}")


if __name__ == "__main__":
    main()
