"""M2 acceptance: a fresh agent can answer from the dogfood node without help.

Brief section 12, M2: *"a new Claude Code session attached to examples/kourob-node answers
'what is a bridge and when does a node stop bridging' with a citation, without asking the
human, in under 10 minutes."*

This is the test that says the repo is actually usable as memory rather than merely
organised. It runs a real agent session, so it is an eval, not a unit test: mark it
`eval` and keep it out of the default local loop.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.m2, pytest.mark.eval]

M2 = "M2 not implemented"

QUESTION = "what is a bridge and when does a node stop bridging"

#: The answer must contain these, from brief section 3.2. A summary that omits the limit
#: has missed the point of the mechanism.
REQUIRED_FACTS = ("bridge_limit", "route")

TIME_BUDGET_SECONDS = 600
PACK_TOKEN_BUDGET = 15_000


@pytest.mark.xfail(reason=M2)
def test_fresh_agent_answers_with_a_citation_inside_the_budget() -> None:
    from kourob.pack import build_pack
    from kourob.testing import fresh_agent_session, kourob_node_path

    node = kourob_node_path()

    with fresh_agent_session(node, adapter="claude_code") as session:
        result = session.ask(QUESTION, timeout=TIME_BUDGET_SECONDS)

    assert result.elapsed_seconds < TIME_BUDGET_SECONDS
    assert not result.asked_the_human, "the agent had to ask; the pack was not enough"
    assert result.citations, "an answer with no citation is not an answer here"
    for fact in REQUIRED_FACTS:
        assert fact in result.text, f"answer omitted {fact}"

    pack = build_pack(node, task="answer a question about bridging")
    assert pack.token_count < PACK_TOKEN_BUDGET, f"pack is {pack.token_count} tokens"


def test_lint_fails_on_an_uncited_claim(tmp_path) -> None:
    """Brief section 12, M2: lint fails on a page containing an uncited claim."""
    from kourob.loops.lint import lint_page

    page = tmp_path / "page.md"
    page.write_text(
        "# Bridging\n\n"
        "A node bridges at most three times per caller and scope. [evt_01J000000000000000000001]\n"
        "\n"
        "Bridging is always faster than referral.\n",  # no citation: this is the bug
        encoding="utf-8",
    )

    flags = lint_page(page)

    uncited = [f for f in flags if f.kind == "uncited_claim"]
    assert uncited, "lint passed a page with an uncited claim"
    assert uncited[0].line == 5
