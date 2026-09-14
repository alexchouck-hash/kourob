"""Trooth in-port: signed provenance envelopes and public scorecards become typed pushes.

Brief reference: section 3 (in-ports), section 7 (the tennis set and friends). KNP-0 I2.

Trooth (github.com/alexchouck-hash/trooth) is the single data connector and provenance pipe:
one MCP server or REST API resolves a request to verified upstream sources, fetches, and
wraps the answer in an envelope carrying the source's identity, licence, timestamps,
freshness lag, content hash and an ed25519 signature. It also publishes a mechanical
scorecard per source on its public site. Both are exactly the kind of thing a cell should
hold as events: dated, sourced, and checkable later.

Two pushes come out of this port:

- `observation.v1` - one per envelope. The payload is the envelope's `data` object kept
  whole, and the provenance fields are lifted beside it so a T0 rule can select on them.
- `scorecard.v1` - one per published scorecard, flattened to the numbers a rule or a
  dashboard asks for.

What is deliberately **not** carried across: `untrusted_text`. Trooth quarantined it as
upstream free text that could carry a prompt injection; a node that re-admitted it into
silver, where a T3 tier reads, would undo the quarantine. It stays out, and the event says
how many strings were dropped so an auditor knows there were some.

This is a port: it translates and knows nothing about answering. Everything it produces
still goes through the gate, which is the only silver writer.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

__milestone__ = "M3"

#: Where Trooth publishes its scorecards today. `fetch_scorecards` reads `manifest.json`
#: there and then one file per source.
PUBLIC_SITE = "https://alexchouck-hash.github.io/trooth-site"
#: The REST API the six tools mirror (Trooth ADR-0006). Not live at the time of writing;
#: `fetch_envelope` is here so the port is complete when it is.
API_BASE = "https://api.trooth.io/v1"
USER_AGENT = "kourob-trooth-port/0.1 (+https://github.com/alexchouck-hash/kourob)"


def _dumps(push: dict[str, Any]) -> str:
    return json.dumps(push, sort_keys=True)


def envelope_to_events(envelope: dict[str, Any]) -> list[str]:
    """One `observation.v1` push from one Trooth envelope (schema/envelope/v0.1).

    `ts` is the *source* timestamp, not the fetch time: the fact happened when the station
    recorded it, and that is the time a later correction has to beat. `fetched_at` and the
    lag between the two are kept as their own fields.
    """
    provenance = envelope["provenance"]
    sources = provenance.get("sources") or []
    primary = next(
        (s for s in sources if s.get("role") == "primary"), sources[0] if sources else {}
    )
    signature = envelope.get("signature") or {}
    push: dict[str, Any] = {
        "schema_ref": "observation.v1",
        "source_id": primary.get("id", "unknown"),
        "query": provenance["resolved_query"],
        "snapshot_id": provenance["snapshot_id"],
        "request_id": envelope.get("request_id", ""),
        "data": envelope.get("data") or {},
        "source_url": primary.get("url", ""),
        "license": primary.get("license", ""),
        "source_timestamp": primary.get("source_timestamp", ""),
        "fetched_at": primary.get("fetched_at", ""),
        "freshness_lag_s": float(primary.get("freshness_lag_s", 0) or 0),
        "content_hash": primary.get("content_hash", ""),
        "served_from": provenance.get("served_from", "live"),
        "considered_and_rejected": provenance.get("considered_and_rejected") or [],
        "disagreements": provenance.get("disagreements") or [],
        "untrusted_text_dropped": len(provenance.get("untrusted_text") or []),
        "signature_alg": signature.get("alg", ""),
        "signature_key_id": signature.get("key_id", ""),
        "signature": signature.get("sig", ""),
        "ts": primary.get("source_timestamp") or provenance.get("fetched_at") or "",
    }
    return [_dumps(push)]


def scorecard_to_events(card: dict[str, Any]) -> list[str]:
    """One `scorecard.v1` push from one published scorecard (schema/scorecard/v0.1)."""
    dims = card.get("dimensions") or {}
    fresh = dims.get("freshness_lag") or {}
    complete = dims.get("completeness_by_segment") or {}
    consistent = dims.get("internal_consistency") or {}
    revision = dims.get("revision_behavior") or {}
    stability = dims.get("schema_stability") or {}
    correction = dims.get("correction_latency") or {}
    accuracy = card.get("accuracy") or {}
    window = card.get("scoring_window") or {}
    push: dict[str, Any] = {
        "schema_ref": "scorecard.v1",
        "source_id": card["source_id"],
        "source_name": card.get("source_name", card["source_id"]),
        "generated_at": card["generated_at"],
        "method_version": str(card.get("method_version", "")),
        "window_start": window.get("start", ""),
        "window_end": window.get("end", ""),
        "snapshot_count": int(window.get("snapshot_count", 0) or 0),
        "freshness_p50_s": fresh.get("p50_seconds"),
        "freshness_p95_s": fresh.get("p95_seconds"),
        "completeness_pct": complete.get("overall_pct"),
        "consistency_pct": consistent.get("consistent_snapshots_pct"),
        "contradictions": int(consistent.get("contradictions_count", 0) or 0),
        "revision_rate_pct": revision.get("revision_rate_pct"),
        "schema_changes": int(stability.get("schema_changes_count", 0) or 0),
        "correction_p95_s": correction.get("p95_seconds"),
        "accuracy_metric": accuracy.get("metric"),
        "accuracy_score": accuracy.get("score"),
        "accuracy_unit": accuracy.get("unit"),
        "ts": card["generated_at"],
    }
    return [_dumps({k: v for k, v in push.items() if v is not None})]


def _kind(doc: dict[str, Any]) -> str | None:
    if "provenance" in doc and "signature" in doc:
        return "envelope"
    if "dimensions" in doc and "source_id" in doc:
        return "scorecard"
    return None  # a manifest, or something else that is not a fact


def document_to_events(doc: dict[str, Any]) -> list[str]:
    kind = _kind(doc)
    if kind == "envelope":
        return envelope_to_events(doc)
    if kind == "scorecard":
        return scorecard_to_events(doc)
    return []


def _documents(path: Path) -> Iterator[dict[str, Any]]:
    """Every JSON object in a file: one object, a list of them, or JSON lines."""
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        yield from (d for d in json.loads(text) if isinstance(d, dict))
        return
    if stripped.startswith("{"):
        try:
            yield json.loads(text)
            return
        except json.JSONDecodeError:
            pass  # not one object: try it as lines
    for line in text.splitlines():
        if line.strip():
            yield json.loads(line)


def tree_to_events(root: Path | str, *, glob: str = "**/*.json*") -> list[str]:
    """Every envelope and scorecard under a path (or in one file), as pushes."""
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.glob(glob))
    out: list[str] = []
    for path in files:
        if any(part.startswith(".") for part in path.parts):
            continue
        for doc in _documents(path):
            out.extend(document_to_events(doc))
    return out


# ---------------------------------------------------------------------------- network


def _get_json(url: str, *, timeout: float = 20.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_scorecards(site: str = PUBLIC_SITE, *, timeout: float = 20.0) -> list[dict[str, Any]]:
    """The scorecards Trooth publishes on its public site, via its manifest."""
    base = site.rstrip("/")
    manifest = _get_json(f"{base}/scorecards/manifest.json", timeout=timeout)
    cards: list[dict[str, Any]] = []
    for entry in manifest.get("sources") or []:
        cards.append(_get_json(f"{base}/scorecards/{entry['source_id']}.json", timeout=timeout))
    return cards


def fetch_envelope(
    *,
    source: str,
    endpoint: str,
    freshness: str = "cached_ok",
    api_base: str = API_BASE,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """`POST /fetch`: one signed envelope from the Trooth API (Trooth ADR-0006)."""
    body = json.dumps({"source": source, "endpoint": endpoint, "freshness": freshness})
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/fetch",
        data=body.encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def events_from(target: str | Path, *, timeout: float = 20.0) -> list[str]:
    """Pushes from a path (file or tree) or from a Trooth site URL (its scorecards).

    This is what `kourob ingest --from-trooth` calls. A URL means the public site: the
    manifest is read and every scorecard it lists becomes a push. Envelopes come from
    files, because the API that serves them is not public yet.
    """
    text = str(target)
    if text.startswith(("http://", "https://")):
        out: list[str] = []
        for card in fetch_scorecards(text, timeout=timeout):
            out.extend(scorecard_to_events(card))
        return out
    return tree_to_events(Path(target))


def documents_to_events(docs: Iterable[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for doc in docs:
        out.extend(document_to_events(doc))
    return out


__all__ = [
    "API_BASE",
    "PUBLIC_SITE",
    "document_to_events",
    "documents_to_events",
    "envelope_to_events",
    "events_from",
    "fetch_envelope",
    "fetch_scorecards",
    "scorecard_to_events",
    "tree_to_events",
]
