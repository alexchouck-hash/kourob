"""`kourob publish`: what a node hands a registry, in the registry's own shapes.

Brief reference: sections 7 and 12 (M5). KNP-4 section 2 (registries, trust).

The first registry a node can be listed in is Trooth's provider catalog
(trooth-site/providers): a data owner lists a feed as one catalog YAML entry, sets a price,
and gets a public six-dimension scorecard. A KouroB node *is* such a feed - it answers typed
questions from held events, meters every request, and signs every receipt - so `publish
--trooth` writes the two documents a provider needs, in Trooth's schemas
(`schema/catalog/v0.1.json`, `schema/scorecard/v0.1.json`):

- **the catalog entry**: the node's identity, scope, held schemas as fields, upstream
  sources as lineage, and its price as a metered cost;
- **the provider scorecard**: the six dimensions computed from the node's own request log,
  receipts, quarantine and outcomes - the same mechanical numbers Trooth publishes for a
  public source, so a node and a source are comparable on one page.

Nothing here advertises what the node cannot show. Every number is a query over what the
node already records; a node with no traffic gets a scorecard that says so.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from kourob import events as ev
from kourob.node import INFRASTRUCTURE_SCHEMAS, Node

__milestone__ = "M5"

METHOD_VERSION = "0.1"
OUT_DIR = "out/trooth"
KNP3_URL = "https://github.com/alexchouck-hash/kourob/blob/main/docs/protocols/knp-3-metering.md"


# --------------------------------------------------------------------------- catalog


def _held_sources(node: Node) -> tuple[list[str], list[str]]:
    """(source ids, licences) seen in held observations, for lineage and licence."""
    if node.store.stats("silver")["rows"] == 0:
        return [], []
    rows = node.store.query(
        "SELECT DISTINCT json_extract_string(payload, '$.source_id') AS s, "
        "json_extract_string(payload, '$.license') AS l FROM silver "
        "WHERE json_extract_string(payload, '$.source_id') IS NOT NULL"
    ).to_pylist()
    sources = sorted({r["s"] for r in rows if r["s"]})
    licences = sorted({r["l"] for r in rows if r["l"]})
    return sources, licences


def catalog_entry(node: Node, *, endpoint_url: str | None = None) -> dict[str, Any]:
    """One Trooth catalog entry (schema/catalog/v0.1) describing this node as a feed."""
    manifest = node.manifest
    sources, licences = _held_sources(node)
    fields: list[dict[str, str]] = []
    for schema_id, contract in sorted(node.contracts.items()):
        if schema_id in INFRASTRUCTURE_SCHEMAS:
            continue
        for prop in contract.fields:
            fields.append(
                {
                    "name": f"{schema_id}.{prop.name}",
                    "type": prop.logical_type,
                    "description": prop.description or f"{prop.name} of {schema_id}",
                }
            )
    rest = manifest.ports.get("rest")
    host = getattr(rest, "host", "127.0.0.1")
    port = getattr(rest, "port", 8080)
    url = endpoint_url or f"http://{host}:{port}/v1/answer"
    pricing = manifest.pricing
    return {
        "id": manifest.identity.name,
        "name": f"KouroB node {manifest.identity.name}",
        "description": manifest.scope.summary,
        "endpoints": [
            {"name": "answer", "url": url, "method": "POST"},
            {"name": "mcp", "url": f"file://{node.dir.resolve().as_posix()}", "method": "POST"},
        ],
        "auth": {"type": "none", "notes": f"caller is identified by did; node {node.did}"},
        "license": {
            "spdx": licences[0] if len(licences) == 1 else "see-upstream",
            "name": "as held: " + (", ".join(licences) or "no licensed sources held yet"),
            "url": "https://github.com/alexchouck-hash/kourob/blob/main/LICENSE",
            "redistribution_allowed": True,
            "attribution_required": True,
            "attribution_text": "Every answer cites the event ids it was made from.",
        },
        "refresh_cadence": str((manifest.loops.get("ingest") or {}).get("trigger", "on_push")),
        "declared_lineage": {
            "role": "derivative",
            "upstream_sources": sources,
            "notes": "A node holds typed events with their provenance and answers from them.",
        },
        "freshness_field": "ts",
        "fields": fields,
        "quirks": [
            "Every request leaves a signed receipt, refusals included.",
            "Answers cite event ids; `kourob trace <receipt>` walks them to the sources.",
            f"Scope is declared: {len(manifest.scope.excludes)} exclusions refer elsewhere.",
        ],
        "cost": {
            "model": "metered",
            "rate_limit": f"{pricing.capacity_window} requests per {pricing.window} before surge",
            "pricing_url": KNP3_URL,
        },
    }


# ------------------------------------------------------------------------- scorecard


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 2) if whole else 100.0


def _p(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(float(ordered[index]), 1)


def _ts(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


def provider_scorecard(node: Node, *, now: datetime | None = None) -> dict[str, Any]:
    """Trooth's six dimensions (schema/scorecard/v0.1), computed from what the node records.

    - freshness lag: answer time minus the newest cited event's time, per answered request;
    - revision behaviour: settled answers later corrected;
    - correction latency: how long a correction took to arrive, from outcomes;
    - completeness: in-scope requests that got an answer, by tier;
    - schema stability: `node_change.v1` events in the window;
    - internal consistency: contradictions the gate quarantined against what silver holds.
    """
    from kourob.ledger.outcomes import read_outcomes

    now = now or ev.now()
    store = node.store
    requests: list[dict[str, Any]] = (
        store.scan("requests", order_by="ts") if store.stats("requests")["rows"] else []
    )
    answered = [
        r
        for r in requests
        if r.get("tier_used") and r.get("scope_result") in ("in_scope", "bridge")
    ]
    in_scope = [r for r in requests if r.get("scope_result") in ("in_scope", "bridge")]

    lags: list[float] = []
    if answered and store.stats("silver")["rows"]:
        ts_by_id = {r["id"]: r["ts"] for r in store.query("SELECT id, ts FROM silver").to_pylist()}
        for r in answered:
            raw = r.get("citations") or []
            ids = raw.split(",") if isinstance(raw, str) else list(raw)
            cited = [ts_by_id.get(c.strip()) for c in ids if c]
            newest = max((t for t in (_ts(c) for c in cited) if t), default=None)
            asked = _ts(r.get("ts"))
            if newest and asked:
                lags.append(max(0.0, (asked - newest).total_seconds()))

    outcomes = read_outcomes(node.ledger) if store.stats("receipts")["rows"] else []
    settled = [o for o in outcomes if o.verdict.value in ("accepted", "corrected")]
    corrected = [o for o in settled if o.verdict.value == "corrected"]
    latencies = [float(o.latency_s) for o in corrected if o.latency_s is not None]

    by_tier: dict[str, float] = {}
    for tier in sorted({r["tier_used"] for r in answered}):
        by_tier[tier] = _pct(sum(1 for r in answered if r["tier_used"] == tier), len(in_scope))

    changes = 0
    if store.stats("silver")["rows"]:
        changes = int(
            store.query(
                "SELECT count(*) AS n FROM silver WHERE schema_ref = 'node_change.v1'"
            ).to_pylist()[0]["n"]
        )
    contradictions = 0
    if store.stats("quarantine")["rows"]:
        contradictions = int(
            store.query(
                "SELECT count(*) AS n FROM quarantine WHERE reason LIKE '%contradict%'"
            ).to_pylist()[0]["n"]
        )
    held = store.stats("silver")["rows"]

    card: dict[str, Any] = {
        "schema_version": "0.1",
        "source_id": node.manifest.identity.name,
        "source_name": f"KouroB node {node.manifest.identity.name}",
        "method_version": METHOD_VERSION,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scoring_window": {
            "start": str(requests[0]["ts"]) if requests else now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": str(requests[-1]["ts"]) if requests else now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_count": len(requests),
        },
        "dimensions": {
            "freshness_lag": {
                "p50_seconds": _p(lags, 0.5) or 0.0,
                "p95_seconds": _p(lags, 0.95) or 0.0,
                "sample_count": len(lags),
            },
            "revision_behavior": {
                "revision_rate_pct": _pct(len(corrected), len(settled)) if settled else 0.0,
                "revised_records_count": len(corrected),
                "total_records_count": len(settled),
            },
            "correction_latency": {
                "p50_seconds": _p(latencies, 0.5),
                "p95_seconds": _p(latencies, 0.95),
                "events_evaluated": len(latencies),
            },
            "completeness_by_segment": {
                "overall_pct": _pct(len(answered), len(in_scope)),
                "segments": by_tier,
            },
            "schema_stability": {
                "stable_snapshots_pct": _pct(held - changes, held) if held else 100.0,
                "schema_changes_count": changes,
            },
            "internal_consistency": {
                "consistent_snapshots_pct": _pct(held, held + contradictions),
                "contradictions_count": contradictions,
            },
        },
    }
    if settled:
        card["accuracy"] = {
            "anchor": "settled outcomes recorded in the node's own ledger (KNP-2 section 4)",
            "metric": "accepted_pct",
            "score": _pct(len(settled) - len(corrected), len(settled)),
            "unit": "percent",
            "sample_count": len(settled),
        }
    return card


# --------------------------------------------------------------------------- publish


def publish_trooth(node: Node, out_dir: Path | str | None = None) -> dict[str, Path]:
    """Write `catalog.yaml` and `scorecard.json` under the node's `out/trooth/`."""
    target = Path(out_dir) if out_dir else node.dir / OUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    catalog = target / "catalog.yaml"
    scorecard = target / "scorecard.json"
    catalog.write_text(
        "# Trooth catalog entry for this node (schema/catalog/v0.1). Generated by kourob publish.\n"
        + yaml.safe_dump(catalog_entry(node), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    scorecard.write_text(
        json.dumps(provider_scorecard(node), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"catalog": catalog, "scorecard": scorecard}


def summarise(card: dict[str, Any]) -> str:
    d = card["dimensions"]
    parts = [
        f"{card['source_id']}: {card['scoring_window']['snapshot_count']} requests",
        f"freshness p50 {d['freshness_lag']['p50_seconds']}s "
        f"p95 {d['freshness_lag']['p95_seconds']}s",
        f"complete {d['completeness_by_segment']['overall_pct']}%",
        f"consistent {d['internal_consistency']['consistent_snapshots_pct']}%",
        f"revisions {d['revision_behavior']['revision_rate_pct']}%",
    ]
    if "accuracy" in card:
        parts.append(f"accepted {card['accuracy']['score']}%")
    return "; ".join(parts)


__all__ = [
    "METHOD_VERSION",
    "OUT_DIR",
    "catalog_entry",
    "provider_scorecard",
    "publish_trooth",
    "summarise",
]
