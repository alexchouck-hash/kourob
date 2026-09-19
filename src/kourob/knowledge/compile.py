"""Compile pages from events. Every claim carries an event id citation.

Brief reference: sections 2 (Page), 6.1 (compile loop), 8 (pages/). KNP-0 I2.

A page is a *view* over events, regenerated from them and never edited by hand: a
hand-written claim has no event id to cite, and the lint loop fails the page. Pages exist so
a human — or an agent's context pack — can read what the node knows without querying it,
and so every sentence they read can be traced the same way an answer can.

Grouping is by the contract's first key field when it has one (`note.v1` groups by topic),
otherwise one page per schema. The claim text is the payload's longest string field, which
is the body of a note and the most useful line of most records; the rest of the payload
rides along compactly so nothing is lost.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kourob import events as ev

__milestone__ = "M2"

PAGES_DIR = "pages"
INDEX = "index.md"
#: Any `[evt_...]` counts as a citation. Not pinned to ULID length: whether the id *exists*
#: is lint's orphan check, and a citation that is well-formed but unknown is a different,
#: more useful flag than one that is merely the wrong length.
CITATION = re.compile(r"\[(evt_[0-9A-Za-z]+)\]")

#: Written at the top of every compiled page. Lint refuses to pass a page without it, and
#: humans get told why their edit will vanish.
HEADER = (
    "<!-- compiled by kourob from events; do not edit - edits are overwritten and a "
    "hand-written claim has no event id to cite -->"
)

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-") or "page"


@dataclass
class Page:
    name: str
    title: str
    schema_ref: str
    claims: list[tuple[str, str]] = field(default_factory=list)  # (text, event_id)
    latest: str = ""

    @property
    def path(self) -> str:
        return f"{self.name}.md"

    def render(self) -> str:
        # Page metadata rides in a comment: it describes the page, not the world, and a
        # sentence about the page would be an uncited claim to the linter - correctly.
        lines = [
            HEADER,
            f"<!-- schema: {self.schema_ref}; claims: {len(self.claims)}; "
            f"latest: {self.latest} -->",
            f"# {self.title}",
            "",
        ]
        for text, event_id in self.claims:
            lines.append(f"- {text} [{event_id}]")
        lines.append("")
        return "\n".join(lines)


@dataclass
class CompileReport:
    pages: list[str] = field(default_factory=list)
    claims: int = 0
    events: int = 0
    skipped: int = 0

    def __str__(self) -> str:
        return (
            f"compiled {len(self.pages)} page(s), {self.claims} claim(s) "
            f"from {self.events} event(s)"
        )


def _claim_text(payload: dict[str, Any], key_field: str | None) -> str:
    """The longest string field is the claim; the rest rides along, compactly."""
    strings = {k: v for k, v in payload.items() if isinstance(v, str) and k != key_field}
    if not strings:
        return json.dumps(payload, sort_keys=True)
    main_key = max(strings, key=lambda k: len(strings[k]))
    rest = {k: v for k, v in payload.items() if k not in (main_key, key_field)}
    tail = f"  ({', '.join(f'{k}={v}' for k, v in sorted(rest.items()))})" if rest else ""
    return f"{strings[main_key]}{tail}"


def compile_pages(node: Any) -> CompileReport:
    """Regenerate every page from silver. Idempotent; stale pages are removed."""
    from kourob.node import INFRASTRUCTURE_SCHEMAS

    pages_dir = Path(node.dir) / PAGES_DIR
    pages_dir.mkdir(parents=True, exist_ok=True)
    report = CompileReport()
    contracts = node.contracts
    pages: dict[str, Page] = {}

    rows = node.store.scan("silver", order_by="id") if node.store.stats("silver")["rows"] else []
    for row in rows:
        schema_ref = str(row.get("schema_ref") or "")
        if schema_ref in INFRASTRUCTURE_SCHEMAS:
            report.skipped += 1
            continue
        payload = row.get("payload") or {}
        contract = contracts.get(schema_ref)
        key_field = contract.key_fields[0] if contract and contract.key_fields else None
        group = str(payload.get(key_field)) if key_field and payload.get(key_field) else None
        name = slug(f"{schema_ref.split('.')[0]}-{group}") if group else slug(schema_ref)
        title = group or schema_ref
        page = pages.setdefault(name, Page(name=name, title=title, schema_ref=schema_ref))
        page.claims.append((_claim_text(payload, key_field), row["id"]))
        page.latest = max(page.latest, str(row.get("ts") or ""))
        report.events += 1

    keep = {INDEX}
    for page in pages.values():
        (pages_dir / page.path).write_text(page.render(), encoding="utf-8")
        report.pages.append(page.path)
        report.claims += len(page.claims)
        keep.add(page.path)
    for stale in pages_dir.glob("*.md"):
        if stale.name in keep:
            continue
        # Compile owns what it generated and nothing else. A generated page nothing produces
        # any more is removed; a hand-written page is left for lint to flag, because
        # silently deleting someone's work is worse than telling them it cannot stay.
        if stale.read_text(encoding="utf-8").startswith(HEADER):
            stale.unlink()

    (pages_dir / INDEX).write_text(_index(node, pages), encoding="utf-8")
    return report


def _index(node: Any, pages: dict[str, Page]) -> str:
    # The index is the node describing its own pages. Its prose is the scope declaration
    # (signed in the card, so it lives in the heading) and page-level metadata (a comment).
    # Neither is a claim about the world, and neither carries a citation.
    lines = [
        HEADER,
        f"<!-- {len(pages)} page(s), compiled {ev.now():%Y-%m-%d %H:%M} UTC; every claim on "
        "every page carries an event id, and `kourob trace` explains any of them -->",
        f"# Index: {node.manifest.scope.summary}",
        "",
    ]
    for page in sorted(pages.values(), key=lambda p: p.name):
        lines.append(
            f"- [{page.title}]({page.path}) - {len(page.claims)} claim(s), `{page.schema_ref}`"
        )
    lines.append("")
    return "\n".join(lines)


def read_page(node: Any, name: str) -> str | None:
    path = Path(node.dir) / PAGES_DIR / (name if name.endswith(".md") else f"{name}.md")
    return path.read_text(encoding="utf-8") if path.exists() else None


def citations_in(text: str) -> list[str]:
    return CITATION.findall(text)


__all__ = [
    "CITATION",
    "HEADER",
    "INDEX",
    "PAGES_DIR",
    "CompileReport",
    "Page",
    "citations_in",
    "compile_pages",
    "read_page",
    "slug",
]
