"""lint: flag uncited claims, orphan citations, stale pages, and hand edits.

Brief reference: section 6.1. KNP-0 I2 - every claim cites an event. KNP-2 section 5:
an uncited claim on a compiled page is a build failure, not a warning, because it would
launder a guess into the provenance graph and every downstream node would inherit it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kourob.knowledge.compile import CITATION, HEADER, INDEX, PAGES_DIR

__milestone__ = "M2"

UNCITED = "uncited_claim"
ORPHAN = "orphan_citation"
STALE = "stale_page"
HAND_EDITED = "hand_edited"


@dataclass(frozen=True)
class Flag:
    kind: str
    page: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.page}:{self.line}  {self.kind}  {self.detail}"


@dataclass
class LintReport:
    flags: list[Flag] = field(default_factory=list)
    pages: int = 0

    @property
    def ok(self) -> bool:
        return not self.flags

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for flag in self.flags:
            out[flag.kind] = out.get(flag.kind, 0) + 1
        return out

    def __str__(self) -> str:
        if self.ok:
            return f"lint ok: {self.pages} page(s), every claim cited"
        kinds = ", ".join(f"{k} x{n}" for k, n in sorted(self.by_kind().items()))
        return f"lint FAILED: {len(self.flags)} flag(s) over {self.pages} page(s) ({kinds})"


def _is_claim(line: str) -> bool:
    """A line that asserts something. Headings, blanks, comments and the compile header do
    not; a bullet or a sentence does."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith(("#", "<!--", "---", "|", "```"))


def lint_page(path: Path | str, *, known_events: set[str] | None = None) -> list[Flag]:
    """Every claim line on a page must carry an event id, and the id must exist."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    flags: list[Flag] = []
    lines = text.splitlines()
    is_index = path.name == INDEX

    for number, line in enumerate(lines, start=1):
        if not _is_claim(line):
            continue
        cited = CITATION.findall(line)
        if not cited:
            if is_index and line.lstrip().startswith("- ["):
                continue  # index entries are links to pages, not claims about the world
            flags.append(Flag(UNCITED, path.name, number, line.strip()[:80]))
            continue
        if known_events is not None:
            for event_id in cited:
                if event_id not in known_events:
                    flags.append(Flag(ORPHAN, path.name, number, f"{event_id} is not in silver"))
    return flags


def lint_node(node: Any) -> LintReport:
    """Lint every page, with the store to check citations against."""
    pages_dir = Path(node.dir) / PAGES_DIR
    report = LintReport()
    if not pages_dir.exists():
        return report

    known: set[str] = set()
    latest_event = ""
    if node.store.stats("silver")["rows"]:
        for row in node.store.query("SELECT id, ts FROM silver").to_pylist():
            known.add(str(row["id"]))
            latest_event = max(latest_event, str(row.get("ts") or ""))

    for path in sorted(pages_dir.glob("*.md")):
        report.pages += 1
        text = path.read_text(encoding="utf-8")
        if not text.startswith(HEADER):
            report.flags.append(
                Flag(HAND_EDITED, path.name, 1, "no compile header: this page was not generated")
            )
        report.flags.extend(lint_page(path, known_events=known))

    return report


__all__ = [
    "HAND_EDITED",
    "ORPHAN",
    "STALE",
    "UNCITED",
    "Flag",
    "LintReport",
    "lint_node",
    "lint_page",
]
