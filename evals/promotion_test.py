"""M5 acceptance: the promotion ladder, and the claims KNP-5 flagged as untested.

Specified in docs/protocols/knp-5-evolution.md sections 3, 5 and 10. Decided in ADR-0008.

KNP-5 section 10 lists five falsifiable claims and said numbers 3 and 5 had no test and
were the two most likely to be wrong. This file is those tests. Claim 3 still needs replayed
traffic over many days (M5, T1); the rest run for real.

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

from kourob.loops.distill.mine import mine_rule, subject_of
from kourob.loops.evolve import MIN_COVERAGE, ProposalKind, evolve
from kourob.testing import (
    cluster_with_an_edge_case,
    correct_one_t0_answer,
    node_with_promoted_rule,
    outcomes_for_tier,
    synthetic_request_log,
    t3_answered_cell,
)
from kourob.tiers.t0_rules import RULES_DIR, load_rules
from kourob.types import Tier

pytestmark = [pytest.mark.m5, pytest.mark.eval]

M5 = "M5 not implemented"


@pytest.mark.xfail(reason=M5)
def test_a_promoted_t0_rule_is_never_corrected_in_the_replay_window(tmp_path) -> None:
    """KNP-5 section 10, claim 3. The core promise of `derived`, over thirty replayed days.

    Needs T1 and `replay_synthetic_traffic`; until then the same promise is checked one
    correction at a time in `test_one_corrected_outcome_disables_a_t0_rule`.
    """
    from kourob.ledger.outcome import Verdict
    from kourob.testing import replay_synthetic_traffic, tennis_node_fixture

    node = tennis_node_fixture(tmp_path)
    replay_synthetic_traffic(node, days=30, requests_per_day=200, evolve_weekly=True)

    corrected = [o for o in outcomes_for_tier(node, Tier.T0) if o.verdict is Verdict.CORRECTED]
    assert not corrected


def test_an_unsettled_cluster_never_promotes_past_t2(tmp_path) -> None:
    """KNP-5 section 10, claim 5. Unverifiable work does not get to be cheap (ADR-0007)."""
    node = synthetic_request_log(
        tmp_path,
        clusters={"opinion.v1": 1.0},
        days=60,
        demand_factor=0.2,
        settle_rate=0.0,  # nothing ever settles: no outcomes arrive
    )

    report = evolve(node)
    promotions = [p for p in report.proposals if p.kind is ProposalKind.PROMOTE]
    assert not promotions, f"promoted an unsettled cluster to {[p.to_tier for p in promotions]}"

    (declined,) = [d for d in report.declined if d.kind is ProposalKind.PROMOTE]
    assert "settle_rate 0" in declined.why


def test_a_function_of_one_event_is_mined_and_replayed_to_t0(tmp_path) -> None:
    """ADR-0008: the cost curve comes from noticing that most of a mature node's traffic is
    a small number of functions being recomputed by a language model."""
    cell = t3_answered_cell(tmp_path, topics=8)

    report = evolve(cell)

    (promotion,) = [p for p in report.proposals if p.kind is ProposalKind.PROMOTE]
    assert promotion.from_tier is Tier.T3 and promotion.to_tier is Tier.T0
    assert promotion.evidence["replay_exact_match"] == 1.0
    assert promotion.evidence["coverage"] == 1.0
    assert promotion.evidence["n"] == 8
    assert "match:" in promotion.evidence["rule_yaml"], "the proposal carries the rule itself"
    assert promotion.payback_requests == 0.0, (
        "a mined rule costs nothing to install, so payback is immediate"
    )


def test_one_corrected_outcome_disables_a_t0_rule(tmp_path) -> None:
    """KNP-5 section 5. No grace period: one counter-example disproves a function."""
    node, rule_id = node_with_promoted_rule(tmp_path)
    assert any(r.id == rule_id for r in load_rules(node)), "the mined rule is live"

    correct_one_t0_answer(node, rule_id)
    report = evolve(node)

    (demotion,) = [
        p
        for p in report.proposals
        if p.kind is ProposalKind.DEMOTE and p.evidence.get("rule") == rule_id
    ]
    assert demotion.evidence["counter_examples"] == 1
    assert demotion.evidence["disabled"] is True
    assert demotion.evidence["inverse"] == {"kind": "enable", "rule": rule_id}
    assert not any(r.id == rule_id for r in load_rules(node)), "disabled in the same run"
    assert (node / RULES_DIR / f"{rule_id}.yaml.disabled").exists(), "renamed, not deleted"


def test_partial_coverage_is_allowed_but_partial_correctness_is_not(tmp_path) -> None:
    """ADR-0008: a rule may decline requests. It may not get them wrong."""
    store, cluster, verdicts = cluster_with_an_edge_case(tmp_path)

    candidate = mine_rule(store, cluster, verdicts)

    assert candidate is not None
    assert candidate.replay_exact_match == 1.0, "a mined rule must be exact on what it covers"
    assert candidate.coverage < 1.0, "this fixture has an edge case the rule should decline"
    assert candidate.coverage >= MIN_COVERAGE
    assert candidate.promotable, "exact plus adequate coverage should promote"
    assert candidate.misses == [], "declining is not missing"


def test_a_near_miss_is_not_a_function(tmp_path) -> None:
    """The gate is exact, not a tolerance. One wrong replay disqualifies the candidate."""
    store, cluster, verdicts = cluster_with_an_edge_case(tmp_path)
    candidate = mine_rule(store, cluster, verdicts)
    assert candidate is not None

    # Sabotage one settled request's cited set so the replay disagrees with it.
    rows = store.scan("requests", order_by="id")
    victim = next(r for r in rows if r["question"] == "what is topic-3")
    from kourob.loops.distill.mine import replay
    from kourob.request_log import RequestRecord

    tampered = [RequestRecord.from_row(r) for r in rows if r["scope_result"] == "in_scope"]
    for record in tampered:
        if record["question"] == victim["question"]:
            record["citations"] = ["evt_SOMETHINGELSE"]
    candidate.replayed = candidate.exact = candidate.covered = 0
    candidate.misses = []
    replay(store, candidate, tampered)

    assert candidate.replay_exact_match < 1.0
    assert not candidate.promotable
    assert candidate.misses, "the miss is named so a human can look at it"


@pytest.mark.parametrize(
    ("question", "subject"),
    [
        ("what is a bridge", "bridge"),
        ("tell me about the pruning loop", "pruning loop"),
        ("What is topic-7?", "topic-7"),
    ],
)
def test_subject_is_the_inverse_of_the_frame(question: str, subject: str) -> None:
    assert subject_of(question) == subject


@pytest.mark.xfail(reason=M5)
def test_scope_shedding_drops_a_schema_nobody_pulls(tmp_path) -> None:
    """KNP-5 section 6. A node's size should track demand, not history."""
    node = synthetic_request_log(
        tmp_path,
        clusters={"shot.v1": 1.0},
        declared_schemas=["shot.v1", "doubles_point.v1"],  # second one never asked about
        days=120,
    )

    (shed,) = [p for p in evolve(node).proposals if p.kind is ProposalKind.SHED]
    assert shed.evidence["schema"] == "doubles_point.v1"
    assert shed.evidence["requests_90d"] == 0
