"""Build the MAUDE method node from source, ask it every question, export the run.

    uv run python examples/maude-method-node/export_site.py --out site/maude.json

The node is built from scratch in a temporary directory on every run: `init`, then the
markdown in-port over `source/`, then the compile loop. Nothing is read from a checked-in
build, so the export is a record of a node that existed a second ago rather than a
description of one that existed once.

Then every compiled topic is asked of that node for real, through `serve.answer`, and the
export carries what the run produced: the node's `did:key`, its whole ledger as the exact
canonical bytes each record was signed over, the ed25519 signature on each one, the events
the answers cited, and the receipt each answer was charged against.

A browser given this file can decode the public key out of the `did:key`, check every
signature with WebCrypto, and walk the chain's `prev` back to the genesis anchor. The page
does not ask to be believed about any of it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from kourob import identity, serve
from kourob import node as node_mod
from kourob.ledger.chain import Ledger, fields_for, genesis_prev, signed_view
from kourob.loops import compile as compile_loop
from kourob.ports.files import markdown_tree_to_notes
from kourob.store.parquet_duckdb import ParquetDuckDBStore

HERE = Path(__file__).resolve().parent
SCOPE = "the MAUDE distinct-event method and what its numbers may claim"

#: The order the topics are shown in. A heading missing from here still exports; it just
#: sorts after these, so adding a heading to the source never silently drops it.
ORDER: tuple[str, ...] = (
    "the-question",
    "why-reports-outnumber-events",
    "why-the-error-matters",
    "why-the-corrected-number-is-not-published",
    "no-denominator",
    "a-report-is-not-a-finding",
    "the-programme-boundary",
    "the-method",
    "exact-linkage",
    "fuzzy-linkage",
    "confirming-a-pair",
    "duplicate-rate",
    "versioning-the-method",
    "the-validation-set",
    "holding-the-gold-out",
    "the-acceptance-floor",
    "enforcing-the-floor",
    "the-fixture-rule",
    "the-review-record",
    "dispositioning-the-method",
    "what-the-numbers-may-not-say",
    "what-is-not-built-yet",
    "the-maude-distinct-event-method",
)

#: Topics grouped into the sections the page renders. A topic in no group still appears,
#: under "other", so the grouping is presentation and never a filter.
SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "The problem",
        "Why a report count and an event count are different numbers.",
        (
            "the-question",
            "why-reports-outnumber-events",
            "why-the-error-matters",
            "why-the-corrected-number-is-not-published",
        ),
    ),
    (
        "What the data cannot say",
        "Three structural limits, each fixed by the dataset rather than by the method.",
        ("no-denominator", "a-report-is-not-a-finding", "the-programme-boundary"),
    ),
    (
        "The method",
        "Two deterministic passes, versioned, published in full.",
        (
            "the-method",
            "exact-linkage",
            "fuzzy-linkage",
            "confirming-a-pair",
            "duplicate-rate",
            "versioning-the-method",
        ),
    ),
    (
        "How we know whether it works",
        "The part usually left out: the validation set and the floor the build enforces.",
        (
            "the-validation-set",
            "holding-the-gold-out",
            "the-acceptance-floor",
            "enforcing-the-floor",
            "the-fixture-rule",
        ),
    ),
    (
        "The review record",
        "What makes an export usable in a file somebody signs.",
        ("the-review-record", "dispositioning-the-method"),
    ),
    (
        "The limits, stated on the output",
        "Carried by the answer itself, not by a footnote under it.",
        ("what-the-numbers-may-not-say", "what-is-not-built-yet"),
    ),
    (
        "About the node itself",
        "One claim the node holds about how it was built.",
        ("the-maude-distinct-event-method",),
    ),
)


def build(workdir: Path) -> node_mod.Node:
    """init, ingest, compile. The three commands from the README, in process."""
    node = node_mod.init(workdir, name="maude-method-node", scope=SCOPE)
    source = HERE / "source"
    report = node.gate.ingest_lines(markdown_tree_to_notes(source), source=str(source))
    if report.rejected:
        raise SystemExit(f"gate quarantined {report.rejected}: {report.reasons}")
    compile_loop.run(workdir)
    return node_mod.open_node(workdir)


def _records(node: node_mod.Node) -> list[dict[str, Any]]:
    """Every record in the chain, as the bytes it was signed over plus its signature."""
    store = ParquetDuckDBStore(node.dir, partition_by=node.manifest.store.partition_by)
    out: list[dict[str, Any]] = []
    for record in Ledger(node.dir, store, node.did).records():
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


def _event(node: node_mod.Node, event_id: str) -> dict[str, Any] | None:
    row = node.store.get("silver", event_id)
    if row is None:
        return None
    provenance = row.get("provenance") or {}
    payload = row.get("payload") or {}
    return {
        "id": row["id"],
        "schema_ref": row.get("schema_ref"),
        "ts": str(row.get("ts")),
        # `payload.source` is where the in-port put file#heading; `provenance.source` is
        # only the channel the event arrived on, which is always "push" here.
        "source": payload.get("source"),
        "channel": provenance.get("source"),
        "topic": payload.get("topic"),
        "body": payload.get("body"),
    }


def _topics(node: node_mod.Node) -> list[str]:
    """Compiled topics, in ORDER first and then whatever else the source produced."""
    seen = {
        str(row["payload"]["topic"])
        for row in node.store.scan("silver", order_by="id")
        if (row.get("payload") or {}).get("topic")
    }
    ranked = [t for t in ORDER if t in seen]
    return ranked + sorted(seen - set(ranked))


def _telemetry(node: node_mod.Node, receipt_id: str) -> dict[str, Any]:
    for row in node.store.scan("requests", order_by="id"):
        if row.get("receipt_id") == receipt_id:
            tried = row.get("tiers_tried") or []
            if isinstance(tried, str):
                tried = [t for t in tried.split(",") if t]
            return {
                "decided_by": row.get("decided_by"),
                "tiers_tried": list(tried),
                "latency_ms": round(float(row.get("latency_ms") or 0.0), 2),
                "cost_credits": float(row.get("cost_credits") or 0.0),
                "price_credits": float(row.get("price_credits") or 0.0),
            }
    return {}


def _ask(node: node_mod.Node, topic: str, events: dict[str, Any]) -> dict[str, Any]:
    """One real request. `what is <topic>` is the shape a mined T0 rule binds."""
    answered = serve.answer(node, f"what is {topic}", caller="site-export")
    for event_id in answered.citations:
        found = _event(node, event_id)
        if found is not None:
            events[event_id] = found
    return {
        "topic": topic,
        "question": f"what is {topic}",
        "rendered": answered.rendered,
        "tier": answered.tier_used.value if answered.tier_used else None,
        "determinism": answered.determinism.value if answered.determinism else None,
        "scope_result": str(answered.scope_result.value),
        "citations": list(answered.citations),
        "receipt": answered.receipt_id,
        **_telemetry(node, answered.receipt_id),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="site/maude.json", help="where to write the export")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="maude-node-"))
    try:
        node = build(workdir / "node")
        events: dict[str, Any] = {}
        answers = [_ask(node, topic, events) for topic in _topics(node)]
        grouped = {topic: answer for answer in answers for topic in [answer["topic"]]}
        placed = {t for _, _, topics in SECTIONS for t in topics}
        sections = [
            {
                "title": title,
                "blurb": blurb,
                "answers": [grouped[t] for t in topics if t in grouped],
            }
            for title, blurb, topics in SECTIONS
        ] + [
            {
                "title": "Other",
                "blurb": "Topics in the source that no section claims.",
                "answers": [a for a in answers if a["topic"] not in placed],
            }
        ]
        export = {
            "generated_at": max(str(e["ts"]) for e in events.values()),
            "node": {
                "name": node.manifest.identity.name,
                "did": node.did,
                "scope": SCOPE,
                "autonomy": str(node.manifest.autonomy.level),
                "source_file": "examples/maude-method-node/source/maude-distinct-events.md",
                "genesis_prev": genesis_prev(node.did),
            },
            "counts": {
                "events": len(events),
                "answers": len(answers),
                "records": 0,
            },
            "sections": [s for s in sections if s["answers"]],
            "answers": answers,
            "events": events,
            "records": _records(node),
        }
        export["counts"]["records"] = len(export["records"])

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(export, indent=2, sort_keys=False), encoding="utf-8")
        print(
            f"wrote {out}: {len(answers)} answer(s), {len(events)} event(s), "
            f"{len(export['records'])} ledger record(s), node {node.did}"
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
