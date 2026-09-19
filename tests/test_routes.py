"""The route table: connecting, Hebbian strength, decay, and learning from hints.

Brief reference: KNP-4 section 3, KNP-9 sections 1, 3 and 4.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kourob import node as node_mod
from kourob.manifest import PrunePolicy
from kourob.routes import SOURCE_CONNECT, SOURCE_REFERRAL, Route, RouteTable, keywords_of
from kourob.testing import node_with_events
from kourob.types import RouteHint

pytestmark = pytest.mark.m3


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    a = node_with_events(tmp_path, name="a", scope="notes about the design")
    b = node_with_events(tmp_path, name="b", scope="tennis shot events for charted matches")
    return a, b


# ------------------------------------------------------------------------------ connect


def test_connect_is_one_row_and_no_import(pair: tuple[Path, Path]) -> None:
    a, b = pair
    route = node_mod.connect(node_mod.open_node(a), b)

    table = RouteTable.load(a)
    assert table.get(route.node) is not None
    assert route.source == SOURCE_CONNECT
    assert route.endpoint == str(b.resolve())
    assert "tennis" in route.keywords
    assert not any(p.suffix == ".py" for p in (a / "routes").rglob("*")), (
        "a connection is data, not code: nothing generated, nothing imported"
    )


def test_a_cell_cannot_connect_to_itself(pair: tuple[Path, Path]) -> None:
    a, _ = pair
    with pytest.raises(ValueError, match="itself"):
        node_mod.connect(node_mod.open_node(a), a)


def test_lookup_matches_on_the_neighbours_declared_words(pair: tuple[Path, Path]) -> None:
    a, b = pair
    node_mod.connect(node_mod.open_node(a), b)
    table = RouteTable.load(a)

    assert table.lookup("who hit the most tennis shots").node == node_mod.open_node(b).did
    assert table.lookup("what is a bridge") is None, "no declared word matched: no guess"


# ------------------------------------------------------------------------------ hebbian


def _table(tmp_path: Path) -> RouteTable:
    a = node_with_events(tmp_path, name="a")
    node = node_mod.open_node(a)
    table = RouteTable(node.store, PrunePolicy(hebbian_alpha=0.3, hebbian_beta=0.5))
    table.save(Route(node="did:key:z6MkN", endpoint="", strength=0.5, keywords=["x"]))
    return table


def test_success_raises_strength_and_failure_punishes_harder(tmp_path: Path) -> None:
    """KNP-9 section 3: failure is punished harder than success is rewarded."""
    table = _table(tmp_path)

    up = table.reinforce("did:key:z6MkN", success=True).strength
    assert up == pytest.approx(0.5 + 0.3 * 0.5)

    down = table.reinforce("did:key:z6MkN", success=False).strength
    assert down == pytest.approx(up * 0.5)
    assert (up - 0.5) < (up - down), "one failure undid more than one success gave"


def test_observation_beats_advertisement(tmp_path: Path) -> None:
    """KNP-4 section 3: the price in the score is the price the receipts saw."""
    table = _table(tmp_path)
    cheap = table.reinforce("did:key:z6MkN", success=True, price=0.001).score()
    dear = table.reinforce("did:key:z6MkN", success=True, price=0.1).score()
    assert cheap > dear


def test_decay_fades_everything_and_reports_what_fell(tmp_path: Path) -> None:
    table = _table(tmp_path)
    table.policy.decay_per_window = 0.1
    table.policy.prune_floor = 0.06

    fallen = table.decay()

    assert fallen == 1
    assert table.get("did:key:z6MkN").strength == pytest.approx(0.05)
    assert table.lookup("x") is None, "below the floor, a route is not offered"


def test_updates_are_appended_and_the_latest_wins(tmp_path: Path) -> None:
    """The store is append-only; a route is updated by writing a newer row."""
    table = _table(tmp_path)
    table.reinforce("did:key:z6MkN", success=True)
    table.reinforce("did:key:z6MkN", success=True)

    assert table.store.stats("routes")["rows"] == 3
    reloaded = RouteTable(table.store, table.policy)
    assert reloaded.get("did:key:z6MkN").successes == 2


# ------------------------------------------------------------------------------ learning


def test_a_caller_learns_a_route_from_a_hint(tmp_path: Path) -> None:
    """KNP-1 section 5.2: every caller learns one hop at a time from receipts it paid for."""
    table = _table(tmp_path)
    hint = RouteHint(
        node="did:key:z6MkB",
        scope="tennis shot events",
        endpoint="/somewhere",
        schemas=["shot.v1"],
        cost_credits=0.004,
        evidence="rcpt_01J",
    )

    (learned,) = table.learn([hint])

    assert learned.source == SOURCE_REFERRAL
    assert learned.strength == pytest.approx(0.4), "hearsay starts weaker than a connect"
    assert learned.keywords == keywords_of("tennis shot events")
    assert learned.observed_price == 0.004
    assert learned.evidence == "rcpt_01J"
    assert table.lookup("tennis").node == "did:key:z6MkB"


def test_learning_a_known_route_updates_rather_than_duplicates(tmp_path: Path) -> None:
    table = _table(tmp_path)
    table.learn([RouteHint(node="did:key:z6MkN", scope="x", cost_credits=0.5)])
    assert len(table.routes) == 1
    assert table.get("did:key:z6MkN").observed_price == 0.5


def test_a_hint_without_a_node_is_ignored(tmp_path: Path) -> None:
    table = _table(tmp_path)
    assert table.learn([{"scope": "nothing"}]) == []
