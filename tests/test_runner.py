"""The runner, the local adapter, and T3's refusal to launder a guess.

Brief reference: section 9 (Runner). Grounding: KNP-0 I2, KNP-2 section 5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob import serve
from kourob.runner import Runner
from kourob.runner.adapters import AdapterError, LocalAdapter, Message, ScriptedReply, build
from kourob.runner.adapters.base import estimate_tokens
from kourob.tiers.t3_frontier import T3Frontier, _parse
from kourob.types import ScopeResult, Tier


@pytest.fixture
def cell(tmp_path: Path):
    """A node with the template's starter contract, rule and fixtures already ingested."""
    target = tmp_path / "cell"
    node_mod.init(target, scope="the KouroB design, as notes")
    node_mod.open_node(target).gate.ingest_file(target / "fixtures" / "events.jsonl")
    return node_mod.open_node(target)


def _topics(cell) -> dict[str, str]:
    return {row["payload"]["topic"]: row["id"] for row in cell.store.scan("silver")}


def _runner(cell, replies: list[ScriptedReply]) -> Runner:
    return Runner(
        cell.manifest, store=cell.store, adapters={"local": LocalAdapter.scripted(replies)}
    )


# ------------------------------------------------------------------------------- runner


def test_a_call_is_logged_with_tier_tokens_and_cost(cell) -> None:
    runner = _runner(
        cell, [ScriptedReply(when="hello", text="hi", prompt_tokens=9, completion_tokens=1)]
    )
    runner.call([Message("user", "hello")], tier=Tier.T3, purpose="answer")

    (row,) = cell.store.scan("calls")
    assert row["tier"] == "T3"
    assert row["purpose"] == "answer"
    assert row["prompt_tokens"] == 9
    assert row["completion_tokens"] == 1
    assert row["ok"] is True
    assert row["tokens_estimated"] is False


def test_a_failed_call_is_logged_before_it_raises(cell) -> None:
    """A node that only remembers its successes cannot know its own reliability."""
    runner = _runner(cell, [])
    with pytest.raises(AdapterError):
        runner.call([Message("user", "unscripted")], tier=Tier.T2, purpose="answer")

    (row,) = cell.store.scan("calls")
    assert row["ok"] is False
    assert row["error"]
    assert row["tier"] == "T2"


def test_cost_is_measured_from_reported_tokens(cell) -> None:
    cell.manifest.pricing.token_rates.pop("local", None)  # fall through to `default`
    runner = _runner(
        cell, [ScriptedReply(when="x", text="y", prompt_tokens=1000, completion_tokens=1000)]
    )
    result = runner.call([Message("user", "x")], tier=Tier.T3, purpose="answer")

    rate = cell.manifest.pricing.token_rate(result.model, result.adapter)
    assert runner.price(result) == pytest.approx(rate.prompt + rate.completion)


def test_an_adapter_that_cannot_count_says_so(cell) -> None:
    """An estimated token count must be distinguishable from a measured one."""
    runner = _runner(cell, [ScriptedReply(when="x", text="a longer reply than the prompt")])
    result = runner.call([Message("user", "x")], tier=Tier.T3, purpose="answer")
    assert result.tokens_estimated is True
    assert result.completion_tokens == estimate_tokens("a longer reply than the prompt")


def test_an_unscripted_call_in_a_test_is_an_error_not_a_guess() -> None:
    adapter = LocalAdapter.scripted([])
    with pytest.raises(AdapterError, match="no reply for this prompt"):
        adapter.complete([Message("user", "anything")])


def test_a_scripted_adapter_never_touches_the_network() -> None:
    """DEFAULTS.md: no network in unit tests. `offline` is what makes that checkable."""
    assert LocalAdapter.scripted([]).offline is True
    assert LocalAdapter.scripted([]).available() is True


def test_unimplemented_adapters_are_named_not_silently_missing() -> None:
    with pytest.raises(AdapterError, match="not implemented yet"):
        build("openai")
    with pytest.raises(AdapterError, match="no adapter"):
        build("nonesuch")


# ------------------------------------------------------------------- T3 and grounding


def _reply(answer: str, citations: list[str], confidence: float = 0.85) -> str:
    return json.dumps({"answer": answer, "citations": citations, "confidence": confidence})


def test_t3_answers_from_events_and_cites_them(cell) -> None:
    topics = _topics(cell)
    runner = _runner(
        cell,
        [
            ScriptedReply(
                when="collected",
                text=_reply(
                    "Events, receipts and outcomes are never collected.", [topics["pruning"]]
                ),
            )
        ],
    )
    answer = serve.answer(cell, "which things are never collected", runner=runner)

    assert answer.tier_used is Tier.T3
    assert answer.citations == [topics["pruning"]]
    assert answer.is_grounded()


def test_t3_declines_when_every_citation_is_fabricated(cell) -> None:
    """KNP-2 section 5: emitting this would launder a guess into the provenance graph."""
    runner = _runner(
        cell,
        [
            ScriptedReply(
                when="collected",
                text=_reply("Everything is collected weekly.", ["evt_TOTALLYMADEUP"], 0.99),
            )
        ],
    )
    answer = serve.answer(cell, "which things are never collected", runner=runner)

    assert answer.scope_result is ScopeResult.REJECT
    assert answer.citations == []
    assert answer.tier_used is None


def test_t3_keeps_the_real_citation_and_drops_the_invented_one(cell) -> None:
    topics = _topics(cell)
    runner = _runner(
        cell,
        [
            ScriptedReply(
                when="collected",
                text=_reply("Events and receipts survive.", [topics["pruning"], "evt_NOPE"], 0.9),
            )
        ],
    )
    tier = T3Frontier(cell.dir, cell.store, runner, cell.manifest)
    from kourob.tiers.base import Request

    result = tier.attempt(Request(question="which things are never collected"))

    assert result.answered
    assert result.citations == [topics["pruning"]]
    assert result.confidence == pytest.approx(0.45), "a fabrication halves confidence"
    assert "fabricated" in result.detail


def test_t3_declines_when_nothing_matches(cell) -> None:
    runner = _runner(cell, [ScriptedReply(when=".*", text=_reply("anything", []))])
    tier = T3Frontier(cell.dir, cell.store, runner, cell.manifest)
    from kourob.tiers.base import Request

    result = tier.attempt(Request(question="zzzz qqqq"))
    assert not result.answered
    assert "no events matched" in result.detail
    assert cell.store.stats("calls")["rows"] == 0, "a miss on retrieval must not cost a call"


def test_a_t0_answerable_question_never_reaches_t3(cell) -> None:
    """The cascade stops at the cheapest tier that clears its bar (brief section 3.1)."""
    runner = _runner(cell, [])  # any T3 call would raise, because nothing is scripted
    answer = serve.answer(cell, "what is a bridge", runner=runner)

    assert answer.tier_used is Tier.T0
    assert cell.store.stats("calls")["rows"] == 0, "T0 answered, so no model was called"


@pytest.mark.parametrize(
    "text",
    [
        '{"answer": "a", "citations": ["evt_1"], "confidence": 0.5}',
        '```json\n{"answer": "a", "citations": ["evt_1"], "confidence": 0.5}\n```',
        'Sure! {"answer": "a", "citations": ["evt_1"], "confidence": 0.5} Hope that helps.',
    ],
)
def test_model_replies_are_parsed_through_fences_and_prose(text: str) -> None:
    parsed = _parse(text)
    assert parsed is not None
    assert parsed["answer"] == "a"
    assert parsed["citations"] == ["evt_1"]


@pytest.mark.parametrize("text", ["not json", "", "{}", '{"citations": []}'])
def test_unparseable_replies_are_a_miss_not_a_crash(text: str) -> None:
    assert _parse(text) is None


def test_confidence_is_clamped_not_trusted() -> None:
    assert _parse('{"answer":"a","confidence":9}')["confidence"] == 1.0
    assert _parse('{"answer":"a","confidence":-3}')["confidence"] == 0.0
    assert _parse('{"answer":"a","confidence":"high"}')["confidence"] == 0.0
