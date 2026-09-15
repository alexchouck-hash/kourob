"""Build the method network, ask the desk every section, export the run the page renders.

    uv run python examples/method-network/export_site.py --out site/maude.json

The network is rebuilt from source in a temporary directory on every run, so the export is a
record of five cells that existed a second ago rather than a description of five that existed
once.

Then every section question is put to `method-desk`, which holds nothing. The desk refers or
bridges to whichever cell owns the question, and the export keeps the whole hop chain: which
cell answered, at which tier, what each hop cost, and the event cited at the end of it. One
question is deliberately outside every cell's scope, so the page can show a refusal that
carries a receipt rather than a guess.

Each cell's ledger is exported as the exact canonical bytes each record was signed over plus
its signature, so a browser checks all five chains itself.

**On tiers.** Every fact here answers at T0 as a lookup against a stored note, which is why
each one is diffable against the event it cites. Connective prose would be T3, a real model
call through `runner/`, and it is only attempted when `--model-url` names a reachable
ollama-compatible server. With none, the export records that no prose was generated and the
page says so. Nothing is written by a model unless a model wrote it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from kourob import identity, serve
from kourob import node as node_mod
from kourob.ledger.chain import Ledger, fields_for, genesis_prev, signed_view
from kourob.ledger.verify import trace
from kourob.store.parquet_duckdb import ParquetDuckDBStore

HERE = Path(__file__).resolve().parent


def _build_module() -> Any:
    """Import the sibling `build.py` without depending on the caller's sys.path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("method_network_build", HERE / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The page, section by section. Each entry is (title, blurb, [(topic, expected_owner)]).
#: `expected_owner` is not used to route - the desk routes. It is recorded so the export can
#: say when the desk sent a question somewhere other than where this file expected, which is
#: a routing fact worth seeing rather than an error worth hiding.
SECTIONS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "What MAUDE structurally is",
        "Properties of the dataset, not of any method applied to it. Held by fda-facts.",
        (
            ("one-event-several-reporters", "fda-facts"),
            ("follow-ups-are-separate-records", "fda-facts"),
            ("identifiers-are-dirty", "fda-facts"),
        ),
    ),
    (
        "What the data cannot say",
        "Three limits fixed by the dataset itself. No method reaches past them.",
        (
            ("no-denominator", "fda-facts"),
            ("a-report-is-not-a-finding", "fda-facts"),
            ("the-summary-reporting-boundary", "fda-facts"),
        ),
    ),
    (
        "The method",
        "Two deterministic passes, versioned. Held by maude-method, which holds no results.",
        (
            ("the-goal-of-the-method", "maude-method"),
            ("exact-linkage", "maude-method"),
            ("fuzzy-linkage", "maude-method"),
            ("confirming-a-candidate-pair", "maude-method"),
            ("clustering", "maude-method"),
            ("duplicate-rate", "maude-method"),
            ("versioning-the-method", "maude-method"),
            ("why-the-corrected-number-is-not-already-published", "maude-method"),
        ),
    ),
    (
        "Whether it works",
        "The only cell allowed to answer this is eval-gates, and its answer is mostly no.",
        (
            ("the-validation-set", "eval-gates"),
            ("holding-the-gold-out", "eval-gates"),
            ("the-precision-target", "eval-gates"),
            ("the-recall-target", "eval-gates"),
            ("what-has-been-measured-so-far", "eval-gates"),
            ("enforcing-the-floor", "eval-gates"),
            ("the-fixture-rule", "eval-gates"),
            ("the-expansion-gate", "eval-gates"),
        ),
    ),
    (
        "What the output may not say",
        "The cell whose job is to say no. Held by claims-policy.",
        (
            ("no-rate", "claims-policy"),
            ("no-causation", "claims-policy"),
            ("no-ranking", "claims-policy"),
            ("always-estimated", "claims-policy"),
            ("the-banned-vocabulary", "claims-policy"),
            ("product-code-level-only", "claims-policy"),
            ("the-honest-gap", "claims-policy"),
        ),
    ),
)

#: How many route hints a caller will follow before giving up. Small enough that a loop
#: cannot hide inside it.
MAX_STEPS = 4

#: Asked on purpose, and expected to fail. No cell holds a safety comparison, the desk knows
#: no cell that does, and the refusal is receipted like any other answer. Showing this is the
#: point: a network that cannot say no is a network whose yes means nothing.
REFUSALS: tuple[tuple[str, str], ...] = (
    ("which device is safer", "A safety comparison. No cell holds one, by policy and by design."),
    (
        "what is the duplicate rate for product code EOB",
        "A result. No run against real data exists.",
    ),
)


def _reachable(url: str | None) -> tuple[bool, str]:
    """Is there an ollama-compatible server to do T3 with? Says why when there is not."""
    if not url:
        return False, "no --model-url given, so no model was called and no prose was generated"
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=4) as response:
            json.load(response)
        return True, "model server reachable"
    except (urllib.error.URLError, OSError, ValueError) as why:
        return False, f"model server at {url} did not answer ({why.__class__.__name__})"


def _ledger_of(node: node_mod.Node) -> Ledger:
    store = ParquetDuckDBStore(node.dir, partition_by=node.manifest.store.partition_by)
    return Ledger(node.dir, store, node.did)


def _records(node: node_mod.Node) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in _ledger_of(node).records():
        kind = record.get("kind", "receipt")
        view = signed_view(record, fields_for(kind))
        out.append(
            {
                "id": record["id"],
                "kind": kind,
                "seq": int(record["seq"]),
                "signed": identity.canonical(view).decode("utf-8"),
                "sig": record["sig"],
            }
        )
    return out


def _event(nodes: dict[str, node_mod.Node], event_id: str) -> dict[str, Any] | None:
    for name, node in nodes.items():
        row = node.store.get("silver", event_id)
        if row is None:
            continue
        payload = row.get("payload") or {}
        return {
            "id": row["id"],
            "held_by": name,
            "ts": str(row.get("ts")),
            # payload.source is file#heading from the in-port; provenance.source is the channel.
            "source": payload.get("source"),
            "topic": payload.get("topic"),
        }
    return None


def _telemetry(nodes: dict[str, node_mod.Node]) -> dict[str, dict[str, Any]]:
    """Every request row in the network, keyed by the receipt it produced."""
    out: dict[str, dict[str, Any]] = {}
    for name, node in nodes.items():
        if node.store.stats("requests")["rows"] == 0:
            continue
        for row in node.store.scan("requests", order_by="id"):
            receipt = row.get("receipt_id")
            if not receipt:
                continue
            tried = row.get("tiers_tried") or []
            if isinstance(tried, str):
                tried = [t for t in tried.split(",") if t]
            out[receipt] = {
                "cell": name,
                "decided_by": row.get("decided_by"),
                "tiers_tried": list(tried),
                "latency_ms": round(float(row.get("latency_ms") or 0.0), 2),
                "cost_credits": float(row.get("cost_credits") or 0.0),
                "price_credits": float(row.get("price_credits") or 0.0),
            }
    return out


def _ask(
    desk: node_mod.Node,
    nodes: dict[str, node_mod.Node],
    by_did: dict[str, str],
    question: str,
    events: dict[str, Any],
) -> dict[str, Any]:
    """One request to the desk, following any route it hands back.

    The desk bridges for a caller once and then refers, which is the point of the referral
    design: the second question is answered with a route rather than a fetch, and a caller
    that keeps the route stops paying for the middle hop. So this is written as a caller
    that follows hints, not as one that expects to be carried every time. `path` records
    where it actually went.
    """
    path = [by_did.get(desk.did, "method-desk")]
    answered = serve.answer(desk, question, caller="site-export")
    answering_node = desk
    for _ in range(MAX_STEPS):
        hints = list(getattr(answered, "route_hints", []) or [])
        if answered.citations or not hints:
            break
        first = hints[0]
        target = by_did.get(getattr(first, "node", None) or getattr(first, "did", None))
        if target is None or target not in nodes:
            break
        answering_node = nodes[target]
        path.append(target)
        answered = serve.answer(answering_node, question, caller="site-export")
    chain = trace(answering_node.dir, answered.receipt_id)
    for event_id in answered.citations:
        found = _event(nodes, event_id)
        if found is not None:
            events[event_id] = found
    telemetry = _telemetry(nodes)
    hops = [
        {
            "cell": by_did.get(record.get("node"), "?"),
            "receipt": record["id"],
            "scope": record.get("scope"),
            "tier": record.get("tier"),
            **{k: v for k, v in telemetry.get(record["id"], {}).items() if k != "cell"},
        }
        for record in chain.receipts
    ]
    # trace walks a receipt to its upstream, so hops[0] is the desk and hops[-1] answered.
    answered_by = hops[-1]["cell"] if hops else None
    return {
        "question": question,
        "rendered": answered.rendered,
        "tier": answered.tier_used.value if answered.tier_used else None,
        "determinism": answered.determinism.value if answered.determinism else None,
        "scope_result": str(answered.scope_result.value),
        "citations": list(answered.citations),
        "receipt": answered.receipt_id,
        "answered_by": answered_by,
        "path": path,
        "followed_route": len(path) > 1,
        "hops": hops,
        "hop_count": len(hops),
        "price_credits": round(sum(h.get("price_credits", 0.0) for h in hops), 8),
        "latency_ms": round(sum(h.get("latency_ms", 0.0) for h in hops), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="site/maude.json")
    parser.add_argument(
        "--model-url",
        default=None,
        help="ollama-compatible base url for T3 connective prose. Without it, none is generated.",
    )
    args = parser.parse_args()

    has_model, model_note = _reachable(args.model_url)

    workdir = Path(tempfile.mkdtemp(prefix="method-network-"))
    try:
        nodes = _build_module().build(workdir / "cells")
        desk = nodes["method-desk"]
        by_did = {node.did: name for name, node in nodes.items()}
        events: dict[str, Any] = {}

        sections = []
        surprises = []
        for title, blurb, topics in SECTIONS:
            answers = []
            for topic, expected in topics:
                answer = _ask(desk, nodes, by_did, f"what is {topic}", events)
                answer["topic"] = topic
                answer["expected_owner"] = expected
                if answer["answered_by"] != expected:
                    surprises.append(
                        f"{topic}: expected {expected}, answered by {answer['answered_by']}"
                    )
                answers.append(answer)
            sections.append({"title": title, "blurb": blurb, "answers": answers})

        refusals = []
        for question, why in REFUSALS:
            refused = _ask(desk, nodes, by_did, question, events)
            refused["why_asked"] = why
            refusals.append(refused)

        cells = {
            name: {
                "did": node.did,
                "genesis_prev": genesis_prev(node.did),
                "scope": node.manifest.scope.summary,
                "events": int(node.store.stats("silver")["rows"]),
                "records": _records(node),
            }
            for name, node in nodes.items()
        }

        export = {
            "network": {
                "cells": len(nodes),
                "desk": "method-desk",
                "source_dir": "examples/method-network/source",
                "prose": {"generated": has_model, "note": model_note},
            },
            "counts": {
                "events": sum(c["events"] for c in cells.values()),
                "answers": sum(len(s["answers"]) for s in sections),
                "refusals": len(refusals),
                "records": sum(len(c["records"]) for c in cells.values()),
            },
            "sections": sections,
            "refusals": refusals,
            "events": events,
            "cells": cells,
            "routing_surprises": surprises,
        }

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(export, indent=2), encoding="utf-8")
        print(
            f"wrote {out}: {export['counts']['answers']} answers across "
            f"{len(nodes)} cells, {export['counts']['refusals']} refusals, "
            f"{export['counts']['records']} ledger records"
        )
        print(f"  prose: {model_note}")
        for surprise in surprises:
            print(f"  routing surprise: {surprise}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
