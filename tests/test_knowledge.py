"""Compile and lint: pages from events, a citation on every claim.

Brief reference: section 6.1, section 12 M2. KNP-0 I2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob.knowledge.compile import HEADER, PAGES_DIR, citations_in, compile_pages, read_page
from kourob.loops.lint import HAND_EDITED, ORPHAN, UNCITED, lint_node, lint_page
from kourob.loops.tend import tend
from kourob.ports.mcp import handle
from kourob.testing import node_with_events
from kourob.types import Determinism

pytestmark = pytest.mark.m2


@pytest.fixture
def cell(tmp_path: Path) -> Path:
    return node_with_events(tmp_path, scope="the KouroB design, as notes")


def test_every_compiled_claim_carries_an_event_id(cell: Path) -> None:
    node = node_mod.open_node(cell)
    report = compile_pages(node)

    assert report.pages and report.claims == 6, "six starter notes, six claims"
    for name in report.pages:
        text = read_page(node, name)
        assert text is not None and text.startswith(HEADER)
        claims = [line for line in text.splitlines() if line.startswith("- ")]
        assert claims and all(citations_in(line) for line in claims)
    assert lint_node(node).ok


def test_pages_group_by_the_contracts_key_field(cell: Path) -> None:
    node = node_mod.open_node(cell)
    compile_pages(node)
    page = read_page(node, "note-bridge")
    assert page is not None and "# bridge" in page
    assert "bridge_limit" in page, "the body is the claim"
    index = read_page(node, "index")
    assert index is not None and "[bridge](note-bridge.md)" in index


def test_compile_is_idempotent_and_removes_stale_pages(cell: Path) -> None:
    node = node_mod.open_node(cell)
    compile_pages(node)
    stray = cell / PAGES_DIR / "note-nothing.md"
    stray.write_text(f"{HEADER}\n# nothing\n", encoding="utf-8")

    first = compile_pages(node)
    second = compile_pages(node)

    assert not stray.exists(), "a page nothing produced is removed"
    assert first.pages == second.pages and first.claims == second.claims


def test_the_change_log_is_not_compiled_into_pages(cell: Path) -> None:
    """A change the cell made to itself is infrastructure, not world."""
    from kourob.loops.tend import record_change

    node = node_mod.open_node(cell)
    record_change(
        node, kind="tune", target="x", level="A1", inverse={"kind": "tune", "target": "x"}
    )
    report = compile_pages(node_mod.open_node(cell))
    assert report.skipped == 1
    assert not any("node-change" in p for p in report.pages)


# --------------------------------------------------------------------------------- lint


def test_lint_names_the_uncited_line(tmp_path: Path) -> None:
    page = tmp_path / "p.md"
    page.write_text(
        f"{HEADER}\n# Bridging\n\n- cited [evt_01J1]\n- uncited claim\n\nA bare sentence.\n",
        encoding="utf-8",
    )
    flags = lint_page(page)
    assert [(f.kind, f.line) for f in flags] == [(UNCITED, 5), (UNCITED, 7)]


def test_lint_flags_a_citation_that_is_not_in_silver(cell: Path) -> None:
    node = node_mod.open_node(cell)
    compile_pages(node)
    page = cell / PAGES_DIR / "note-bridge.md"
    page.write_text(page.read_text(encoding="utf-8") + "- a claim [evt_NOPE]\n", encoding="utf-8")

    report = lint_node(node)
    assert [f.kind for f in report.flags] == [ORPHAN]
    assert "evt_NOPE" in report.flags[0].detail


def test_lint_flags_a_hand_written_page(cell: Path) -> None:
    node = node_mod.open_node(cell)
    compile_pages(node)
    (cell / PAGES_DIR / "mine.md").write_text(
        "# Mine\n\nI wrote this. [evt_01J]\n", encoding="utf-8"
    )

    kinds = {f.kind for f in lint_node(node).flags}
    assert HAND_EDITED in kinds and ORPHAN in kinds


# --------------------------------------------------------------------------- consumers


def test_get_page_serves_the_compiled_page_with_its_citations(cell: Path) -> None:
    node = node_mod.open_node(cell)
    compile_pages(node)

    page = handle(cell, "get_page", {"page": "note-bridge"})
    assert page.citations and all(c.startswith("evt_") for c in page.citations)
    assert page.is_grounded() and page.determinism is None

    index = handle(cell, "get_page", {"page": "index"})
    assert index.citations == [] and index.determinism is Determinism.DECLARED
    assert index.is_grounded(), "the index is the node describing its own pages"


def test_tend_compiles_and_halts_on_a_page_lint_would_not_pass(cell: Path) -> None:
    ok = tend(cell, autonomy_max="A0")
    assert ok.compiled >= 1 and ok.lint_flags == 0 and not ok.halted

    (cell / PAGES_DIR / "note-bridge.md").write_text(
        "# bridge\n\nan unsourced claim\n", encoding="utf-8"
    )
    # compile rewrites it, so the hand edit is gone by the time lint runs...
    again = tend(cell, autonomy_max="A0")
    assert not again.halted, "compile regenerates the page before lint sees the edit"

    (cell / PAGES_DIR / "handwritten.md").write_text(
        "# hw\n\nan unsourced claim\n", encoding="utf-8"
    )
    halted = tend(cell, autonomy_max="A0")
    assert halted.halted and "lint FAILED" in (halted.halt_reason or "")
