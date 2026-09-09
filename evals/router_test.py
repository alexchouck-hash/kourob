"""M3 acceptance: referral, bridge, and route learning.

Brief section 12, M3 and section 3.2. The whole point of the bridge is that a caller only
ever needs it once: after the first bridged answer the caller holds a direct route, and
the bridging node stops bridging that (caller, scope) pair after `bridge_limit`.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.m3, pytest.mark.eval]

M3 = "M3 not implemented"


@pytest.mark.xfail(reason=M3)
def test_first_call_bridges_and_returns_a_route_hint(tmp_path) -> None:
    from kourob.testing import two_node_fixture

    from kourob.routes import RouteTable

    kourob_node, tennis_node, caller = two_node_fixture(tmp_path)

    answer = caller.ask(kourob_node, "how many backhand winners did A hit at AO 2026")

    assert answer.scope_result == "bridge"
    assert answer.route_hints, "a bridge must hand back a direct route"
    assert answer.route_hints[0].node == tennis_node.did
    assert answer.citations, "the bridged answer still cites the events behind it"

    assert RouteTable.load(caller.dir).lookup("tennis").node == tennis_node.did


@pytest.mark.xfail(reason=M3)
def test_second_call_is_referred_not_bridged(tmp_path) -> None:
    from kourob.testing import two_node_fixture

    kourob_node, tennis_node, caller = two_node_fixture(tmp_path, bridge_limit=1)

    caller.ask(kourob_node, "how many backhand winners did A hit at AO 2026")
    second = caller.ask(kourob_node, "how many forehand winners did B hit at AO 2026")

    assert second.scope_result == "referral"
    assert second.route_hints[0].node == tennis_node.did


@pytest.mark.xfail(reason=M3)
def test_a_request_whose_hop_list_contains_this_node_is_refused(tmp_path) -> None:
    from kourob.testing import two_node_fixture

    kourob_node, _tennis, caller = two_node_fixture(tmp_path)

    answer = caller.ask(kourob_node, "anything", hops=[kourob_node.did])

    assert answer.scope_result == "reject"
    assert "hop" in answer.rendered.lower()


@pytest.mark.xfail(reason=M3)
def test_trace_shows_both_nodes_both_receipts_and_the_cited_events(tmp_path) -> None:
    from kourob.testing import two_node_fixture

    from kourob.ledger.verify import trace

    kourob_node, tennis_node, caller = two_node_fixture(tmp_path)
    answer = caller.ask(kourob_node, "how many backhand winners did A hit at AO 2026")

    chain = trace(kourob_node.dir, answer.receipt_id)

    assert {n.did for n in chain.nodes} == {kourob_node.did, tennis_node.did}
    assert len(chain.receipts) == 2
    assert chain.events, "trace must reach the events the answer cited"
