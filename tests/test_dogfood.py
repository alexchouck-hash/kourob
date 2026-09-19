"""The repo is the first node: a cell serves this project's own docs with a citation.

Brief reference: section 0 item 7 and section 12 M2 - "the project's own docs must be
served by a KouroB node". The fresh-agent eval (a real Claude Code session) stays in
`evals/`; this proves the same thing with a scripted model and no human.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.knowledge.compile import compile_pages
from kourob.loops.lint import lint_node
from kourob.ports.files import markdown_to_notes, markdown_tree_to_notes, slug
from kourob.testing import _scripted_grounded_runner

REPO = Path(__file__).resolve().parents[1]
PROTOCOLS = REPO / "docs" / "protocols"

pytestmark = pytest.mark.m2


@pytest.fixture
def dogfood(tmp_path: Path) -> Path:
    cell = tmp_path / "kourob-node"
    node_mod.init(cell, name="kourob-node", scope="the KouroB design and this repository")
    lines = markdown_tree_to_notes(PROTOCOLS, relative_to=REPO)
    report = node_mod.open_node(cell).gate.ingest_lines(lines, source="docs/protocols")
    assert report.accepted > 100, f"the protocols are hundreds of paragraphs: {report.reasons}"
    return cell


def test_markdown_becomes_cited_notes_with_a_source_per_paragraph() -> None:
    pushes = markdown_to_notes(PROTOCOLS / "knp-1-scope.md", root=REPO)
    import json

    notes = [json.loads(p) for p in pushes]
    assert all(n["schema_ref"] == "note.v1" for n in notes)
    assert all(n["source"].startswith("docs/protocols/knp-1-scope.md#") for n in notes)
    topics = {n["topic"] for n in notes}
    assert slug("5. Bridging") in topics
    assert all(len(n["body"]) >= 40 for n in notes), "fragments are not claims"
    assert not any("```" in n["body"] for n in notes), "code is reached through its file"


def test_the_repo_compiles_into_lint_clean_pages(dogfood: Path) -> None:
    node = node_mod.open_node(dogfood)
    report = compile_pages(node)
    assert len(report.pages) > 20
    assert lint_node(node).ok


def test_the_dogfood_node_answers_what_a_bridge_is_with_a_citation(dogfood: Path) -> None:
    """The M2 acceptance question, answered from this repository's own words."""
    node = node_mod.open_node(dogfood)
    answer = serve.answer(
        node,
        "what is a bridge and when does a node stop bridging",
        runner=_scripted_grounded_runner(node),
    )

    assert answer.is_grounded() and answer.citations
    cited = node.store.get("silver", answer.citations[0])
    assert cited is not None
    assert "bridg" in cited["payload"]["body"].lower()
    assert cited["payload"]["source"].startswith("docs/protocols/")
    assert answer.receipt_id.startswith("rcpt_")


def test_the_dogfood_node_stays_inside_its_cell_ceiling(dogfood: Path) -> None:
    from kourob.node import cell_size

    size = cell_size(node_mod.open_node(dogfood))
    assert size["over"] == [], f"the dogfood node is over its ceiling: {size}"
