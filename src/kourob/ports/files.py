"""File in-port: turn documents on disk into typed pushes for the gate.

Brief reference: section 3 (in-ports), section 7.19 dogfood. KNP-0 I2.

The first in-port is markdown-to-notes: every paragraph under a heading becomes a `note.v1`
push whose topic is the heading's slug and whose source is the file and heading it came
from. That is enough for a cell to serve a repository's own docs with a citation on every
sentence, which is what the dogfood node is for.

This is a port: it translates and knows nothing about answering. Everything it produces
still goes through the gate, which is the only silver writer.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

__milestone__ = "M2"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SLUG = re.compile(r"[^a-z0-9]+")
_FENCE = "```"
MIN_PARAGRAPH = 40


def slug(text: str, *, limit: int = 64) -> str:
    """A `note.v1` topic: lower-case, hyphenated, within the contract's pattern."""
    out = _SLUG.sub("-", text.lower()).strip("-")[:limit].strip("-")
    return out if len(out) >= 2 else "untitled"


def _paragraphs(lines: list[str]) -> Iterator[str]:
    """Blank-line-separated blocks, with fenced code and tables left out.

    Code and tables are not claims a page should restate as sentences; they are better
    reached through the file they live in, which the note's `source` names.
    """
    block: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith(_FENCE):
            in_fence = not in_fence
            block = []
            continue
        if in_fence or line.lstrip().startswith("|"):
            continue
        if line.strip():
            block.append(line.strip())
        elif block:
            yield " ".join(block)
            block = []
    if block:
        yield " ".join(block)


def markdown_to_notes(
    path: Path | str, *, root: Path | str | None = None, ts: datetime | None = None
) -> list[str]:
    """JSONL lines of `note.v1` pushes, one per paragraph, topic from the nearest heading."""
    path = Path(path)
    rel = path.relative_to(root) if root else path
    stamp = (ts or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    pushes: list[str] = []
    heading = path.stem
    section: list[str] = []

    def flush() -> None:
        for para in _paragraphs(section):
            if len(para) < MIN_PARAGRAPH:
                continue
            pushes.append(
                json.dumps(
                    {
                        "schema_ref": "note.v1",
                        "topic": slug(heading),
                        "body": para,
                        "source": f"{rel.as_posix()}#{slug(heading)}",
                        "ts": stamp,
                    }
                )
            )

    for line in lines:
        match = _HEADING.match(line)
        if match:
            flush()
            section = []
            heading = match.group(2)
        else:
            section.append(line)
    flush()
    return pushes


def markdown_tree_to_notes(
    root: Path | str, *, glob: str = "**/*.md", relative_to: Path | str | None = None
) -> list[str]:
    """Every markdown file under `root`. Sources are relative to `relative_to` (default:
    `root`), so a repository can cite `docs/protocols/x.md#h` rather than `x.md#h`."""
    root = Path(root)
    base = Path(relative_to) if relative_to else root
    out: list[str] = []
    for path in sorted(root.glob(glob)):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        out.extend(markdown_to_notes(path, root=base))
    return out


__all__ = ["MIN_PARAGRAPH", "markdown_to_notes", "markdown_tree_to_notes", "slug"]
