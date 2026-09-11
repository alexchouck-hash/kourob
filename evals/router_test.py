"""M3 acceptance: referral, bridge, and route learning.

Brief section 12, M3 and section 3.2. The whole point of the bridge is that a caller only
ever needs it once: after the first bridged answer the caller holds a direct route, and the
bridging node stops bridging that (caller, scope) pair after `bridge_limit`.

Run on the local transport: two cells on disk, one that declares tennis out of scope and
names the other. Nothing crosses by import even here — the neighbour is opened by path and
asked over `serve.answer`, exactly as a remote one would be asked over the wire.
"""

from __future__ import annotations

import pytest

from kourob.ledger.verify import trace, verify
from kourob.routes import RouteTable
from kourob.testing import two_node_fixture
from kourob.types import RefusalReason, ScopeResult

pytestmark = [pytest.mark.m3, pytest.mark.eval]

TENNIS_QUESTION = "shot 1 of point p001 in match ao-2026-f-01"


def test_first_call_bridges_and_returns_a_route_hint(tmp_path) -> None:
    kourob_node, tennis_node, caller = two_node_fixture(tmp_path)

    answer = caller.ask(kourob_node, TENNIS_QUESTION)

    assert answer.scope_result is ScopeResult.BRIDGE
    assert answer.route_hints, "a bridge must hand back a direct route"
    assert answer.route_hints[0].node == tennis_node.did
    assert answer.route_hints[0].evidence, "a hint with no evidence receipt is hearsay"
    assert answer.citations, "the bridged answer still cites the events behind it"
    assert answer.data is not None
    assert answer.is_grounded()

    learned = RouteTable.load(caller.dir).lookup("tennis shot")
    assert learned is not None and learned.node == tennis_node.did, (
        "the caller learns the direct route from the receipt it already paid for"
    )


def test_second_call_is_referred_not_bridged(tmp_path) -> None:
    kourob_node, tennis_node, caller = two_node_fixture(tmp_path, bridge_limit=1)

    first = caller.ask(kourob_node, TENNIS_QUESTION)
    second = caller.ask(kourob_node, "shot 2 of point p001 in match ao-2026-f-01")

    assert first.scope_result is ScopeResult.BRIDGE
    assert second.scope_result is ScopeResult.REFERRAL
    assert second.route_hints[0].node == tennis_node.did
    assert second.citations == [], "a referral asserts nothing and cites nothing"
    assert "go direct" in second.rendered


def test_the_caller_can_then_go_direct(tmp_path) -> None:
    """The network converges: one paid introduction, then a direct route forever."""
    kourob_node, tennis_node, caller = two_node_fixture(tmp_path, bridge_limit=1)
    caller.ask(kourob_node, TENNIS_QUESTION)

    direct = caller.ask(tennis_node, TENNIS_QUESTION)

    assert direct.scope_result is ScopeResult.IN_SCOPE
    assert direct.tier_used is not None
    assert direct.citations


def test_a_request_whose_hop_list_contains_this_node_is_refused(tmp_path) -> None:
    kourob_node, _tennis, caller = two_node_fixture(tmp_path)

    answer = caller.ask(kourob_node, "anything at all", hops=[kourob_node.did])

    assert answer.scope_result is ScopeResult.REJECT
    assert answer.reason is RefusalReason.LOOP
    assert "hop" in answer.rendered.lower()
    assert answer.receipt_id.startswith("rcpt_"), "a refusal is receipted like any answer"


def test_a_hop_budget_is_enforced_before_any_tier_runs(tmp_path) -> None:
    kourob_node, _tennis, caller = two_node_fixture(tmp_path)
    too_many = [f"did:key:z6Mk{i:040d}" for i in range(4)]  # max_hops defaults to 4

    answer = caller.ask(kourob_node, "what is a bridge", hops=too_many)

    assert answer.scope_result is ScopeResult.REJECT
    assert answer.reason is RefusalReason.HOPS_EXHAUSTED


def test_trace_shows_both_nodes_both_receipts_and_the_cited_events(tmp_path) -> None:
    kourob_node, tennis_node, caller = two_node_fixture(tmp_path)
    answer = caller.ask(kourob_node, TENNIS_QUESTION)

    chain = trace(kourob_node.dir, answer.receipt_id)

    assert set(chain.nodes) == {kourob_node.did, tennis_node.did}
    assert len(chain.receipts) == 2
    upstream = [r for r in chain.receipts if r["node"] == tennis_node.did]
    assert upstream and upstream[0]["scope_result"] == "in_scope"
    assert chain.events, "trace must reach the events the answer cited"
    assert chain.events[0]["schema_ref"] == "shot.v1"
    assert not chain.unreachable

    assert verify(kourob_node.dir).ok and verify(tennis_node.dir).ok, (
        "both chains stay valid: each node signed its own receipt in its own ledger"
    )


def test_a_referral_with_a_declared_exclusion_names_the_rule(tmp_path) -> None:
    """KNP-1 section 3: the receipt records which rule decided, so evolve can mine it."""
    kourob_node, _tennis, caller = two_node_fixture(tmp_path, bridge_limit=0)

    answer = caller.ask(kourob_node, "how did the tennis match go")

    assert answer.scope_result is ScopeResult.REFERRAL
    decided = answer.metadata["https://kourob.org/ext/scope/v1/decided_by"]
    assert decided.startswith("rule:excl-")
    assert answer.metadata["https://kourob.org/ext/scope/v1/bridge"] == {
        "used": 0,
        "limit": 0,
        "resets": None,
    }


def test_a_successful_bridge_strengthens_the_route(tmp_path) -> None:
    """KNP-9 section 3: Hebbian. The route the bridge used is stronger afterwards."""
    kourob_node, tennis_node, caller = two_node_fixture(tmp_path)
    before = RouteTable.load(kourob_node.dir).get(tennis_node.did).strength

    caller.ask(kourob_node, TENNIS_QUESTION)

    after = RouteTable.load(kourob_node.dir).get(tennis_node.did)
    assert after.strength > before
    assert after.successes == 1
    assert after.evidence and after.evidence.startswith("rcpt_")
