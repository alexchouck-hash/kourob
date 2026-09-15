"""Export one real run of the network as JSON a web page can verify for itself.

    uv run python examples/trooth-network/export_web.py --out site/network.json

Builds the seven cells, asks the front desk a handful of questions for real, then writes
out what the run actually produced: each node's `did:key`, its whole ledger as the exact
canonical bytes each record was signed over, the ed25519 signature on each one, and the
events the answers cited.

Nothing here is a description of a receipt. It is the receipt: a browser given this file
can decode the public key out of the `did:key`, check every signature with WebCrypto, and
walk each chain's `prev` back to the genesis anchor without asking anyone to be believed.
That is the whole point of the export - a page that says "verified" and means it.

The one thing a static page cannot do is answer a new question, so the questions are fixed
and the answers are the ones this run got.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from kourob import identity, serve
from kourob import node as node_mod
from kourob.ledger.chain import Ledger, fields_for, genesis_prev, signed_view
from kourob.ledger.verify import trace
from kourob.store.parquet_duckdb import ParquetDuckDBStore

HERE = Path(__file__).resolve().parent

#: The questions the page offers, each asked of the front desk by its own caller.
ASKS: tuple[tuple[str, str, str], ...] = (
    (
        "weather",
        "nws observation at KJFK",
        "Two referrals deep: the front desk holds nothing, and neither does the weather desk.",
    ),
    (
        "quake",
        "largest earthquake in the last hour",
        "One hop. The front desk refers seismic questions straight to the node that holds them.",
    ),
    (
        "cpi",
        "what is the latest cpi",
        "One hop, to the node holding the BLS consumer price index.",
    ),
    (
        "model",
        "open-meteo observation at KJFK",
        "The weather desk has already spent its one introduction with the front desk, so "
        "nobody bridges this time. Watch the caller follow the hints instead - which is the "
        "point of handing them out.",
    ),
)

#: Asked a second time by the caller who already used its introduction, so the page can show
#: what a caller that has been given the route gets instead of another bridge.
REPEAT = ("weather", "nws observation at KJFK")

#: How many hints a caller will follow before giving up. Three is enough for this network
#: and small enough that a loop cannot hide in it.
MAX_STEPS = 4


def _build_module() -> Any:
    """Import the sibling `build.py`, whose directory name has a dash in it."""
    spec = importlib.util.spec_from_file_location("trooth_network_build", HERE / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ledger_of(node: node_mod.Node) -> Ledger:
    store = ParquetDuckDBStore(node.dir, partition_by=node.manifest.store.partition_by)
    return Ledger(node.dir, store, node.did)


def _records(node: node_mod.Node) -> list[dict[str, Any]]:
    """Every record in one node's chain, as the bytes it was signed over plus its signature.

    `signed` is `identity.canonical(signed_view(record))` decoded as UTF-8 - byte for byte
    what the node put through ed25519. The page parses this string for display, so what a
    reader sees is necessarily what was signed; there is no second copy to disagree with it.
    """
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


def _telemetry(nodes: dict[str, node_mod.Node]) -> dict[str, dict[str, Any]]:
    """Every request row in the network, keyed by the receipt it produced.

    `decided_by` is the one-line reason plan 06 section 4.3 asks every routing decision to
    carry; `tiers_tried` is what the cascade considered and rejected before the tier that
    answered; `shape` is the class signature a class memo would key on.
    """
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
                "node": name,
                "decided_by": row.get("decided_by"),
                "tiers_tried": list(tried),
                "shape": row.get("shape"),
                "latency_ms": round(float(row.get("latency_ms") or 0.0), 2),
                "cost_credits": float(row.get("cost_credits") or 0.0),
                "price_credits": float(row.get("price_credits") or 0.0),
            }
    return out


def _event(store: ParquetDuckDBStore, event_id: str) -> dict[str, Any] | None:
    row = store.get("silver", event_id)
    if row is None:
        return None
    provenance = row.get("provenance") or {}
    return {
        "id": row["id"],
        "schema_ref": row.get("schema_ref"),
        "ts": str(row.get("ts")),
        "source": provenance.get("source"),
        "agent": provenance.get("agent"),
        "payload": row.get("payload") or {},
    }


def _scope_summary(node: node_mod.Node) -> dict[str, Any]:
    scope = node.manifest.scope
    return {
        "summary": scope.summary if hasattr(scope, "summary") else "",
        "entities": list(scope.entities or []),
        "schemas": list(scope.schemas or []),
        "refers": [
            {"pattern": exclusion.pattern, "to": exclusion.refer_to}
            for exclusion in (scope.excludes or [])
        ],
    }


def _ask(
    node: node_mod.Node,
    question: str,
    caller: str,
    by_did: dict[str, str],
    nodes: dict[str, node_mod.Node],
    events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """One request against one node, with the receipt chain it produced."""
    answered = serve.answer(node, question, caller=caller)
    chain = trace(node.dir, answered.receipt_id)
    for event_id in answered.citations:
        for holder in nodes.values():
            found = _event(holder.store, event_id)
            if found is not None:
                events[event_id] = found
                break
    telemetry = _telemetry(nodes)
    hops = [
        {
            "node": by_did.get(record.get("node"), "?"),
            "receipt": record["id"],
            **telemetry.get(record["id"], {}),
        }
        for record in chain.receipts
    ]
    return {
        "asked": by_did.get(node.did, "?"),
        "hops": hops,
        "cost_credits": round(sum(h.get("cost_credits", 0.0) for h in hops), 6),
        "price_credits": round(sum(h.get("price_credits", 0.0) for h in hops), 6),
        "latency_ms": round(sum(h.get("latency_ms", 0.0) for h in hops), 2),
        "rendered": answered.rendered,
        "scope_result": str(answered.scope_result.value),
        "tier": answered.tier_used.value if answered.tier_used else None,
        "determinism": answered.determinism.value if answered.determinism else None,
        "citations": list(answered.citations),
        # trace walks a receipt to its upstream, which is the order the question travelled.
        "receipts": [record["id"] for record in chain.receipts],
        "path": [by_did.get(record.get("node"), "?") for record in chain.receipts],
        "hints": [
            {
                "to": by_did.get(hint.node, hint.node),
                "did": hint.node,
                "scope": hint.scope,
                "evidence": hint.evidence,
            }
            for hint in (answered.route_hints or [])
        ],
        "_hint_dids": [hint.node for hint in (answered.route_hints or [])],
    }


def _thread(
    key: str,
    question: str,
    note: str,
    caller: str,
    front: node_mod.Node,
    nodes: dict[str, node_mod.Node],
    by_did: dict[str, str],
    events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Ask the front desk, then follow whatever route it hands back until answered.

    A caller that is referred is not stuck: it was told who can answer. Following the hint
    is what a real caller does, and it is the reason a network of desks gets shorter with
    use rather than longer.
    """
    by_name = {node.did: node for node in nodes.values()}
    steps: list[dict[str, Any]] = []
    here = front
    for _ in range(MAX_STEPS):
        step = _ask(here, question, caller, by_did, nodes, events)
        hints = step.pop("_hint_dids")
        steps.append(step)
        if step["scope_result"] != "referral" or not hints:
            break
        nxt = by_name.get(hints[0])
        if nxt is None:
            break
        here = nxt
    return {
        "key": key,
        "question": question,
        "note": note,
        "caller": caller,
        "steps": steps,
        "totals": {
            "asks": len(steps),
            "hops": sum(len(step["hops"]) for step in steps),
            "cost_credits": round(sum(step["cost_credits"] for step in steps), 6),
            "price_credits": round(sum(step["price_credits"] for step in steps), 6),
            "latency_ms": round(sum(step["latency_ms"] for step in steps), 2),
        },
    }


def export(root: Path) -> dict[str, Any]:
    build = _build_module()
    nodes, _refused = build.build(root)
    front = nodes["trooth-desk"]
    by_did = {node.did: name for name, node in nodes.items()}

    events: dict[str, dict[str, Any]] = {}
    threads = [
        _thread(key, question, note, f"user:web-{key}", front, nodes, by_did, events)
        for key, question, note in ASKS
    ]

    repeat_key, repeat_question = REPEAT
    threads.append(
        _thread(
            f"{repeat_key}-again",
            repeat_question,
            "The same caller asks again. Its one introduction is spent, so the desk refers "
            "instead of bridging - and the hint it hands back is the direct route it learned "
            "the first time. Follow it and the answer costs one hop instead of three.",
            f"user:web-{repeat_key}",
            front,
            nodes,
            by_did,
            events,
        )
    )

    ledgers: dict[str, Any] = {}
    for name, node in nodes.items():
        ledgers[name] = {
            "did": node.did,
            "genesis_prev": genesis_prev(node.did),
            "records": _records(node),
        }

    return {
        "generated_by": "examples/trooth-network/export_web.py",
        "what_this_is": (
            "One real run of the seven-cell trooth-network. Every `signed` string is the "
            "exact canonical JSON its node put through ed25519; every `sig` is that "
            "signature, base58. A reader recovers each public key from its did:key and "
            "checks both the signatures and the prev-chain without trusting this file."
        ),
        "nodes": [
            {
                "name": name,
                "did": node.did,
                "kind": "desk" if node.store.stats("silver")["rows"] == 0 else "source",
                "events": node.store.stats("silver")["rows"],
                "scope": _scope_summary(node),
            }
            for name, node in nodes.items()
        ],
        "threads": threads,
        "events": events,
        "ledgers": ledgers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="where to write the JSON")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="build the cells here instead of a temporary directory",
    )
    args = parser.parse_args()

    temp = None
    if args.root is None:
        temp = Path(tempfile.mkdtemp(prefix="kourob-export-"))
        root = temp / "cells"
    else:
        root = args.root
        if root.exists():
            shutil.rmtree(root)

    try:
        payload = export(root)
    finally:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=False), encoding="utf-8")

    records = sum(len(entry["records"]) for entry in payload["ledgers"].values())
    print(f"{args.out}: {len(payload['threads'])} threads, {records} signed records,")
    print(f"{len(payload['events'])} cited events, {len(payload['nodes'])} nodes")


if __name__ == "__main__":
    main()
