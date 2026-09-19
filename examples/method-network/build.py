"""Build the method network: four cells that each own one domain, and a desk that owns none.

    uv run python examples/method-network/build.py

- **fda-facts**: what MAUDE structurally is. No denominator, a report is not a finding, the
  summary reporting boundary, and why reports outnumber events.
- **maude-method**: the two deduplication passes, the thresholds, and the versioning rule.
- **eval-gates**: the difference between a target and a result, and the fact that nothing has
  been measured yet.
- **claims-policy**: the language rules. The cell whose job is to say no.
- **method-desk**: the front. Holds nothing at all and refers each question to whoever owns it.

The split is the point. A question about precision reaches `eval-gates`, which answers that
0.85 is a target and that nothing has been measured, because that is the only cell allowed to
say so. `maude-method` holds the threshold but no result, and `claims-policy` holds neither.
Which cell answered is visible in the receipt chain rather than hidden behind a single voice.

Nothing generated is committed: the cells land in `cells/`, gitignored.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob.ports import files as files_port
from kourob.ports.files import markdown_tree_to_notes

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
DEFAULT_ROOT = HERE / "cells"

#: One cell per domain: id -> scope summary. The summary is what `kourob connect` advertises
#: and what a caller sees when a desk hands back a route, so it is written for a reader.
CELLS: dict[str, str] = {
    "fda-facts": (
        "what the FDA MAUDE dataset structurally is: no denominator, reports are not findings, "
        "the summary reporting boundary, why one event produces several reports, follow-up "
        "records, and dirty identifiers"
    ),
    "maude-method": (
        "the MAUDE deduplication method version 0.1: exact linkage, fuzzy linkage, the candidate "
        "pair conditions, clustering, duplicate rate, and how the method is versioned"
    ),
    "eval-gates": (
        "whether the deduplication method works: the validation set, held-out gold, the precision "
        "and recall targets, what has actually been measured, and the gates the build enforces"
    ),
    "claims-policy": (
        "what any output carrying these numbers may and may not say: no rate, no causation, no "
        "ranking, always estimated, the banned vocabulary, and the honest gap rule"
    ),
}

#: Extra natural-language hooks per cell, on top of the slugs derived from the source itself,
#: so a person can ask in their own words. The derived slugs are what the page uses.
ALIASES: dict[str, str] = {
    "fda-facts": r"maude structure|what maude (is|contains)|underreport",
    "maude-method": r"how (is|are) .*dedup|linkage|jaccard|union.?find",
    "eval-gates": r"does it work|how good is|accuracy|error rate",
    "claims-policy": r"what may (it|we) (not )?say|language rule|allowed to say",
}


def topics_of(cell_id: str) -> list[str]:
    """Every heading slug in a cell's source, in file order.

    Routing is derived from the source rather than hand-maintained beside it, so a heading
    added to a document is routable the moment it exists. A hand-written pattern list drifts
    from the content the first time somebody renames a heading, and the failure is silent:
    the desk stops referring and tries to answer from a store it does not have.
    """
    out: list[str] = []
    for path in sorted((SOURCE / cell_id).glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                out.append(files_port.slug(line.lstrip("#").strip()))
    return out


def desk_routes() -> dict[str, str]:
    """cell -> the regex the desk uses to send a question there.

    An exact alternation over that cell's own slugs, longest first, plus its aliases. Exact
    because the slugs overlap in substrings that would cross-route if matched loosely:
    `no-rate` belongs to claims-policy while `duplicate-rate` belongs to maude-method, and
    `no-denominator` is fda-facts while `no-causation` is claims-policy.
    """
    routes: dict[str, str] = {}
    for cell_id in CELLS:
        slugs = sorted(set(topics_of(cell_id)), key=len, reverse=True)
        alternation = "|".join(re.escape(slug) for slug in slugs)
        routes[cell_id] = "(?:" + alternation + ")|(?:" + ALIASES[cell_id] + ")"
    return routes


def _fresh_cell(cell: Path, name: str, scope: str) -> Path:
    """A cell with the template's own starter fixtures cleared out.

    The note contract and the note-lookup rule stay: this network answers notes, and that
    rule is what binds `what is <topic>` at T0.
    """
    node_mod.init(cell, name=name, scope=scope)
    shutil.rmtree(cell / "fixtures", ignore_errors=True)
    return cell


def _specialist(root: Path, cell_id: str) -> node_mod.Node:
    """One domain cell, holding only its own source directory."""
    cell = _fresh_cell(root / cell_id, cell_id, CELLS[cell_id])
    node = node_mod.open_node(cell)
    source = SOURCE / cell_id
    report = node.gate.ingest_lines(markdown_tree_to_notes(source), source=str(source))
    if report.rejected:
        raise SystemExit(f"{cell_id}: gate quarantined {report.rejected}: {report.reasons}")
    return node_mod.open_node(cell)


def _desk(root: Path, dids: dict[str, str]) -> node_mod.Node:
    """The front desk. Holds nothing, and every exclusion names the cell that does."""
    cell = _fresh_cell(
        root / "method-desk",
        "method-desk",
        "the front desk for the MAUDE method note: holds nothing, and refers each question to "
        "the cell that owns it",
    )
    # A desk holds no notes, so a note-lookup rule on it is not just useless, it is fatal:
    # T0 runs before the miss is declared and binds `schema_ref` against an empty silver,
    # which DuckDB rejects because an empty store has no columns to bind. Filed as kb-gpc.
    (cell / "tiers" / "t0" / "rules" / "note-lookup.yaml").unlink(missing_ok=True)
    node = node_mod.open_node(cell)
    routes = desk_routes()
    node.manifest.scope.excludes = [
        manifest_mod.Exclusion(pattern=pattern, refer_to=dids[target])
        for target, pattern in routes.items()
    ]
    node.manifest.bridge.bridge_limit = 1
    manifest_mod.save(cell, node.manifest)
    for target in routes:
        node_mod.connect(node_mod.open_node(cell), root / target)
    return node_mod.open_node(cell)


def build(root: Path | str = DEFAULT_ROOT) -> dict[str, node_mod.Node]:
    """Init five cells, connect the desk to the four specialists."""
    root = Path(root)
    nodes = {cell_id: _specialist(root, cell_id) for cell_id in CELLS}
    nodes["method-desk"] = _desk(root, {cid: n.did for cid, n in nodes.items()})
    return nodes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if args.root.exists():
        shutil.rmtree(args.root)  # an example is rebuilt, not upgraded
    for name, node in build(args.root).items():
        print(f"{name:<16} {node.did}  events {node.store.stats('silver')['rows']}")


if __name__ == "__main__":
    main()
