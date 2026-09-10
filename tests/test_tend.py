"""`kourob tend`: apply within autonomy, propose the rest, record every change with its inverse.

Brief reference: KNP-7 sections 2, 4 and 5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob import serve
from kourob.loops.evolve import Proposal, ProposalKind
from kourob.loops.tend import (
    REQUIRED_LEVEL,
    TendError,
    changes,
    decide,
    rollback,
    tend,
)
from kourob.testing import correct_one_t0_answer, t3_answered_cell
from kourob.tiers.t0_rules import load_rules
from kourob.types import Tier

pytestmark = pytest.mark.m4


def _at(cell: Path, level: str) -> Path:
    node = node_mod.open_node(cell)
    node.manifest.autonomy.level = level  # type: ignore[assignment]
    manifest_mod.save(cell, node.manifest)
    return cell


@pytest.fixture
def mineable(tmp_path: Path) -> Path:
    """A cell where evolve will propose a mined T0 rule."""
    return t3_answered_cell(tmp_path, topics=8)


# ----------------------------------------------------------------------------- decide


def _promotion(rule: str = "mined-note-topic", **extra) -> Proposal:
    return Proposal(
        kind=ProposalKind.PROMOTE,
        from_tier=Tier.T3,
        to_tier=Tier.T0,
        evidence={"rule": rule, "rule_yaml": "id: x\nmatch: x\nsql: x\n", **extra},
    )


def test_a0_applies_nothing(mineable: Path) -> None:
    node = node_mod.open_node(mineable)
    (decision,) = decide(node, [_promotion()], level="A0", budget=1.0)
    assert decision.action == "propose"
    assert "needs A2" in decision.why


def test_a2_applies_a_promotion_and_a3_a_shed(mineable: Path) -> None:
    node = node_mod.open_node(mineable)
    shed = Proposal(kind=ProposalKind.SHED, evidence={"schema": "note_check.v1"})

    at_a2 = {
        d.proposal.kind: d.action for d in decide(node, [_promotion(), shed], level="A2", budget=1)
    }
    assert at_a2 == {ProposalKind.PROMOTE: "apply", ProposalKind.SHED: "propose"}

    at_a3 = {
        d.proposal.kind: d.action for d in decide(node, [_promotion(), shed], level="A3", budget=1)
    }
    assert at_a3 == {ProposalKind.PROMOTE: "apply", ProposalKind.SHED: "apply"}


def test_a_change_with_no_inverse_is_never_auto_applied(mineable: Path) -> None:
    """KNP-7 section 4, question 3. The one that does the real work."""
    node = node_mod.open_node(mineable)
    no_rule = Proposal(kind=ProposalKind.PROMOTE, to_tier=Tier.T0, evidence={})
    split = Proposal(kind=ProposalKind.SPLIT, evidence={"demand_factor": 2.0})

    decisions = decide(node, [no_rule, split], level="A4", budget=100.0)
    assert all(d.action == "propose" for d in decisions)
    assert "no recorded inverse" in decisions[0].why
    assert "needs a human" in decisions[1].why
    assert ProposalKind.SPLIT not in REQUIRED_LEVEL


def test_the_budget_turns_an_apply_into_a_propose(mineable: Path) -> None:
    node = node_mod.open_node(mineable)
    (d,) = decide(node, [_promotion(cost_credits=5.0)], level="A4", budget=1.0)
    assert d.action == "propose" and "budget" in d.why


# ------------------------------------------------------------------------------- tend


def test_tend_at_a2_installs_the_mined_rule_with_its_inverse(mineable: Path) -> None:
    _at(mineable, "A2")

    report = tend(mineable, autonomy_max="A2")

    assert not report.halted
    (applied,) = report.applied
    assert applied.kind == "promote"
    assert applied.inverse == {"kind": "demote", "target": applied.target}
    assert any(r.id == applied.target for r in load_rules(mineable)), "the rule is live"

    (change,) = changes(node_mod.open_node(mineable))
    assert change["payload"]["autonomy_level"] == "A2"
    assert json.loads(change["payload"]["inverse"]) == applied.inverse

    answer = serve.answer(node_mod.open_node(mineable), "what is topic-2")
    assert answer.tier_used is Tier.T0, "the node now answers from the rule it mined"


def test_tend_at_a0_proposes_the_same_rule_and_changes_nothing(mineable: Path) -> None:
    report = tend(mineable, autonomy_max="A0")
    assert report.applied == []
    assert any(p.kind is ProposalKind.PROMOTE for p in report.proposed)
    assert changes(node_mod.open_node(mineable)) == []


def test_autonomy_max_caps_the_manifest_level(mineable: Path) -> None:
    _at(mineable, "A4")
    report = tend(mineable, autonomy_max="A1")
    assert report.effective_level == "A1"
    assert report.applied == []


def test_dry_run_decides_but_applies_nothing(mineable: Path) -> None:
    _at(mineable, "A2")
    report = tend(mineable, autonomy_max="A2", dry_run=True)
    assert any(d["action"] == "apply" for d in report.decisions)
    assert report.applied == []
    assert changes(node_mod.open_node(mineable)) == []


# --------------------------------------------------------------------------- rollback


def test_rollback_applies_the_recorded_inverse(mineable: Path) -> None:
    _at(mineable, "A2")
    (applied,) = tend(mineable, autonomy_max="A2").applied
    assert serve.answer(node_mod.open_node(mineable), "what is topic-3").tier_used is Tier.T0

    rollback_id = rollback(mineable, applied.event_id)

    assert not any(r.id == applied.target for r in load_rules(mineable))
    assert (mineable / "tiers/t0/rules" / f"{applied.target}.yaml.disabled").exists(), (
        "renamed, not deleted"
    )
    answer = serve.answer(node_mod.open_node(mineable), "what is topic-3")
    assert answer.tier_used is not Tier.T0, "the prior state is restored"

    history = changes(node_mod.open_node(mineable))
    assert [c["payload"]["kind"] for c in history] == ["promote", "rollback"]
    assert history[-1]["id"] == rollback_id
    assert history[-1]["payload"]["reverts"] == applied.event_id


def test_rollback_refuses_something_that_is_not_a_change(mineable: Path) -> None:
    with pytest.raises(TendError, match="not a change"):
        rollback(mineable, "evt_00000000000000000000000000")


# ------------------------------------------------------------------------------ halts


def test_a_correction_after_a_promotion_records_the_demotion(mineable: Path) -> None:
    """The demotion itself is evolve's; tend records it with its inverse."""
    _at(mineable, "A2")
    (applied,) = tend(mineable, autonomy_max="A2").applied
    assert serve.answer(node_mod.open_node(mineable), "what is topic-1").tier_used is Tier.T0
    correct_one_t0_answer(mineable, applied.target)

    report = tend(mineable, autonomy_max="A2")

    kinds = [a.kind for a in report.applied]
    assert "demote" in kinds
    demote = next(a for a in report.applied if a.kind == "demote")
    assert demote.inverse == {"kind": "promote", "target": applied.target}


def test_a_broken_ledger_halts_and_demotes_one_level(mineable: Path) -> None:
    from kourob.ledger.verify import tamper_for_test

    _at(mineable, "A2")
    tamper_for_test(mineable, index=0, field="price_credits", value=0.0)

    report = tend(mineable, autonomy_max="A2")

    assert report.halted and "ledger" in (report.halt_reason or "")
    assert report.demoted_to == "A1"
    assert report.applied == []
    assert node_mod.open_node(mineable).manifest.autonomy.level == "A1"


def test_a_halt_at_a0_cannot_demote_further(mineable: Path) -> None:
    from kourob.ledger.verify import tamper_for_test

    tamper_for_test(mineable, index=0, field="price_credits", value=0.0)
    report = tend(mineable, autonomy_max="A0")
    assert report.halted and report.demoted_to is None


def test_two_consecutive_rollbacks_halt(mineable: Path) -> None:
    """KNP-7 section 4.2: something is wrong with the evidence gates themselves."""
    _at(mineable, "A2")
    (applied,) = tend(mineable, autonomy_max="A2").applied
    first = rollback(mineable, applied.event_id)
    rollback(mineable, first)  # rolling back the rollback re-enables; two in a row

    report = tend(mineable, autonomy_max="A2")
    assert report.halted and "rollback" in (report.halt_reason or "")


# --------------------------------------------------------------------------- graduation


def test_graduation_is_suggested_never_set(mineable: Path) -> None:
    _at(mineable, "A2")
    node = node_mod.open_node(mineable)
    node.manifest.autonomy.graduation_window = 2
    manifest_mod.save(mineable, node.manifest)

    first = tend(mineable, autonomy_max="A2")
    second = tend(mineable, autonomy_max="A2")

    assert first.graduation_suggested is None
    assert second.graduation_suggested == "A3"
    assert node_mod.open_node(mineable).manifest.autonomy.level == "A2", (
        "a node cannot promote itself"
    )
