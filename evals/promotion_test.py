"""M5 acceptance: the promotion ladder, and the two claims KNP-5 flagged as untested.

Specified in docs/protocols/knp-5-evolution.md sections 3, 5 and 10. Decided in ADR-0008.

KNP-5 section 10 lists five falsifiable claims and says numbers 3 and 5 have no test and
are the two most likely to be wrong. This file is those tests. Writing them first is the
only way that admission means anything.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.m5, pytest.mark.eval]

M5 = "M5 not implemented"


@pytest.mark.xfail(reason=M5)
def test_a_promoted_t0_rule_is_never_corrected_in_the_replay_window(tmp_path) -> None:
    """KNP-5 section 10, claim 3. The core promise of `derived`.

    A rule promoted by exact replay claims to be a function. If any answer it served during
    the replay window comes back `corrected`, the replay gate let a non-function through and
    ADR-0008 is wrong.
    """
    from kourob.ledger.outcome import Verdict
    from kourob.loops.evolve import evolve
    from kourob.testing import replay_synthetic_traffic, tennis_node_fixture
    from kourob.types import Tier

    node = tennis_node_fixture(tmp_path)
    replay_synthetic_traffic(node, days=30, requests_per_day=200, evolve_weekly=True)

    promoted = [
        p
        for p in evolve(node).proposals
        if p.to_tier is Tier.T0 and p.evidence.get("replay_exact_match") == 1.0
    ]
    assert promoted, "no rule was promoted, so this claim was not exercised"

    from kourob.testing import outcomes_for_tier

    corrected = [o for o in outcomes_for_tier(node, Tier.T0) if o.verdict is Verdict.CORRECTED]
    assert not corrected, (
        f"{len(corrected)} T0 answers were corrected; exact replay admitted a non-function"
    )


def test_an_unsettled_cluster_never_promotes_past_t2(tmp_path) -> None:
    """KNP-5 section 10, claim 5. Unverifiable work does not get to be cheap (ADR-0007)."""
    from kourob.loops.evolve import evolve
    from kourob.testing import synthetic_request_log
    from kourob.types import Tier

    node = synthetic_request_log(
        tmp_path,
        clusters={"opinion.v1": 1.0},
        days=60,
        demand_factor=0.2,
        settle_rate=0.0,  # nothing ever settles: no outcomes arrive
    )

    promotions = [p for p in evolve(node).proposals if p.to_tier in (Tier.T1, Tier.T0)]
    assert not promotions, f"promoted an unsettled cluster to {[p.to_tier for p in promotions]}"


@pytest.mark.xfail(reason=M5)
def test_one_corrected_outcome_disables_a_t0_rule(tmp_path) -> None:
    """KNP-5 section 5. No grace period: one counter-example disproves a function."""
    from kourob.loops.evolve import ProposalKind, evolve
    from kourob.testing import correct_one_t0_answer, node_with_promoted_rule

    node, rule_id = node_with_promoted_rule(tmp_path)
    correct_one_t0_answer(node, rule_id)

    demotions = [
        p
        for p in evolve(node).proposals
        if p.kind is ProposalKind.DEMOTE and p.evidence.get("rule") == rule_id
    ]
    assert demotions, "a corrected T0 answer did not demote its rule"
    assert demotions[0].evidence["counter_examples"] == 1


@pytest.mark.xfail(reason=M5)
def test_partial_coverage_is_allowed_but_partial_correctness_is_not(tmp_path) -> None:
    """ADR-0008: a rule may decline requests. It may not get them wrong."""
    from kourob.loops.distill.calibrate import mine_rule
    from kourob.testing import cluster_with_an_edge_case

    cluster = cluster_with_an_edge_case(tmp_path)
    candidate = mine_rule(cluster)

    assert candidate.replay_exact_match == 1.0, "a mined rule must be exact on what it covers"
    assert candidate.coverage < 1.0, "this fixture has an edge case the rule should decline"
    assert candidate.promotable, "exact plus adequate coverage should promote"


@pytest.mark.xfail(reason=M5)
def test_scope_shedding_drops_a_schema_nobody_pulls(tmp_path) -> None:
    """KNP-5 section 6. A node's size should track demand, not history."""
    from kourob.loops.evolve import ProposalKind, evolve
    from kourob.testing import synthetic_request_log

    node = synthetic_request_log(
        tmp_path,
        clusters={"shot.v1": 1.0},
        declared_schemas=["shot.v1", "doubles_point.v1"],  # second one never asked about
        days=120,
    )

    (shed,) = [p for p in evolve(node).proposals if p.kind is ProposalKind.SHED]
    assert shed.evidence["schema"] == "doubles_point.v1"
    assert shed.evidence["requests_90d"] == 0
