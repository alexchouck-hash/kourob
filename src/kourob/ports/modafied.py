"""Modafied in-port: an independent benchmark's emblem becomes a typed, verified push.

Brief reference: section 3 (in-ports). KNP-0 I2.

Modafied (modafied.org) is an independent public benchmark of data feeds and MCP servers,
funded by Trooth and measured by the same code for everyone. Per source it publishes an
**attestation** (`schema/attestation/v0.1`): a grade, points, six graded dimensions, a rank
in its category, the evidence urls, and two SVG emblems - full and compact - meant to be put
on the provider's own site or README. The attestation's `notice` is part of the contract:

> Mechanically computed from public snapshots. This is a measurement, not an endorsement, a
> verification, or a partnership. It cannot be purchased and it changes without notice when
> the measurement changes.

This port turns one attestation into one `emblem.v1` event, **after verifying it** the way
Modafied's emblems page says a consumer should: the attestation's `evidence.scorecard_sha256`
must match the sha256 Modafied's `manifest.json` lists for `scorecards/<source_id>.json`. A
consumer that cannot verify the hash fails closed, so an attestation that does not match, or
a manifest that does not list it, is not an event. The event keeps the notice verbatim, the
emblem urls, and the trace id, so anything that displays the emblem can say exactly what it
is and link to the evidence.

This is a port: it translates and knows nothing about answering. Everything it produces
still goes through the gate, which is the only silver writer.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

__milestone__ = "M3"

PUBLIC_SITE = "https://alexchouck-hash.github.io/modafied-site"
USER_AGENT = "kourob-modafied-port/0.1 (+https://github.com/alexchouck-hash/kourob)"
DIMENSIONS = (
    "freshness_lag",
    "revision_behavior",
    "correction_latency",
    "completeness_by_segment",
    "schema_stability",
    "internal_consistency",
)


class UnverifiedError(ValueError):
    """The attestation could not be tied to Modafied's manifest. Fail closed."""


def manifest_sha(manifest: dict[str, Any], source_id: str) -> str | None:
    """The sha256 Modafied's manifest lists for `scorecards/<source_id>.json`."""
    for entry in manifest.get("files") or []:
        if entry.get("path") == f"scorecards/{source_id}.json":
            return str(entry.get("sha256") or "") or None
    return None


def verify(attestation: dict[str, Any], manifest: dict[str, Any]) -> str:
    """Return the verified scorecard sha, or raise `UnverifiedError` with the reason."""
    source_id = attestation.get("source_id")
    if not source_id:
        raise UnverifiedError("attestation has no source_id")
    claimed = str((attestation.get("evidence") or {}).get("scorecard_sha256") or "")
    listed = manifest_sha(manifest, str(source_id))
    if not claimed:
        raise UnverifiedError(f"{source_id}: attestation carries no scorecard_sha256")
    if listed is None:
        raise UnverifiedError(f"{source_id}: manifest lists no scorecards/{source_id}.json")
    if claimed != listed:
        raise UnverifiedError(
            f"{source_id}: scorecard_sha256 {claimed[:12]}… is not the manifest's"
        )
    return claimed


def attestation_to_events(attestation: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    """One `emblem.v1` push from one verified attestation."""
    sha = verify(attestation, manifest)
    claim = attestation.get("claim") or {}
    dims = claim.get("dimensions") or {}
    emblem = attestation.get("emblem") or {}
    evidence = attestation.get("evidence") or {}
    rank = attestation.get("rank") or {}
    push: dict[str, Any] = {
        "schema_ref": "emblem.v1",
        "source_id": attestation["source_id"],
        "source_name": attestation.get("source_name") or attestation["source_id"],
        "category": attestation.get("category") or "",
        "grade": claim.get("grade") or "unrated",
        "status": claim.get("status") or "unknown",
        "points": float(claim.get("points") or 0.0),
        "graded_dimensions": int(claim.get("graded_dimensions") or 0),
        "coverage_pct": float(claim.get("coverage_pct") or 0.0),
        "dimensions": {
            name: {
                "grade": (dims.get(name) or {}).get("grade"),
                "value": (dims.get(name) or {}).get("measured_value"),
                "unit": (dims.get(name) or {}).get("measured_unit"),
                "status": (dims.get(name) or {}).get("status"),
            }
            for name in DIMENSIONS
        },
        "rank_position": int(rank.get("position") or 0),
        "rank_of": int(rank.get("of") or 0),
        "trace_id": attestation["trace_id"],
        "trace_url": attestation.get("trace_url") or "",
        "emblem_full": emblem.get("full") or "",
        "emblem_compact": emblem.get("compact") or "",
        "emblem_alt": emblem.get("alt") or "",
        "scorecard_page_url": evidence.get("scorecard_page_url") or "",
        "scorecard_sha256": sha,
        "manifest_generated_at": manifest.get("generated_at") or "",
        "method_version": str(attestation.get("method_version") or ""),
        "rating_version": str(attestation.get("rating_version") or ""),
        "relationship": attestation.get("relationship") or "none",
        "notice": attestation.get("notice") or "",
        "ts": attestation["generated_at"],
    }
    return [json.dumps(push, sort_keys=True)]


def tree_to_events(root: Path | str, *, manifest_path: Path | str | None = None) -> list[str]:
    """Every `<id>.json` attestation under `root`, verified against `manifest.json` there.

    Attestations that fail verification are skipped, not quarantined here: the port cannot
    write quarantine (only the gate can), and a document that is not a fact is not pushed.
    `verified_tree` returns both lists for a caller that wants to know.
    """
    return verified_tree(root, manifest_path=manifest_path)[0]


def verified_tree(
    root: Path | str, *, manifest_path: Path | str | None = None
) -> tuple[list[str], list[str]]:
    root = Path(root)
    manifest = json.loads(Path(manifest_path or root / "manifest.json").read_text(encoding="utf-8"))
    pushes: list[str] = []
    refused: list[str] = []
    for path in sorted(root.glob("*.json")):
        if path.name == "manifest.json":
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "claim" not in doc or "emblem" not in doc:
            continue
        try:
            pushes.extend(attestation_to_events(doc, manifest))
        except UnverifiedError as why:
            refused.append(str(why))
    return pushes, refused


# ---------------------------------------------------------------------------- network


def _get_json(url: str, *, timeout: float = 20.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_attestations(
    source_ids: Iterable[str], *, site: str = PUBLIC_SITE, timeout: float = 20.0
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Live attestations and the manifest they must verify against."""
    base = site.rstrip("/")
    manifest = _get_json(f"{base}/v1/manifest.json", timeout=timeout)
    docs = [_get_json(f"{base}/v1/emblems/{sid}.json", timeout=timeout) for sid in source_ids]
    return docs, manifest


def events_from(target: str | Path, *, source_ids: Iterable[str] = (), timeout: float = 20.0):
    """Pushes from a directory of attestations, or from the Modafied site for `source_ids`."""
    text = str(target)
    if text.startswith(("http://", "https://")):
        docs, manifest = fetch_attestations(source_ids, site=text, timeout=timeout)
        out: list[str] = []
        for doc in docs:
            out.extend(attestation_to_events(doc, manifest))
        return out
    return tree_to_events(Path(target))


def markdown_emblem(push: dict[str, Any]) -> str:
    """The embed Modafied's emblems page prescribes: the full emblem, linked to the card."""
    return f"[![{push['emblem_alt']}]({push['emblem_full']})]({push['scorecard_page_url']})"


__all__ = [
    "DIMENSIONS",
    "PUBLIC_SITE",
    "UnverifiedError",
    "attestation_to_events",
    "events_from",
    "fetch_attestations",
    "manifest_sha",
    "markdown_emblem",
    "tree_to_events",
    "verified_tree",
    "verify",
]
