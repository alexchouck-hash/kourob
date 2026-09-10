"""The KNP protocol surface: extension URIs, envelope grounding, ledger records.

These are contract tests. They fail when the code and docs/protocols/ drift apart, which is
the failure mode a spec suite actually has.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kourob.ledger.outcome import SOURCE_WEIGHT, OutcomeSource, Verdict
from kourob.loops.evolve import ClusterStats, EvolveReport, Objective, Proposal, ProposalKind
from kourob.protocols import EXT_SPEC, Ext, activation_header, key, parse_activation
from kourob.types import TIER_DETERMINISM, Answer, Determinism, RefusalReason, ScopeResult, Tier

PROTOCOL_DOCS = Path(__file__).resolve().parents[1] / "docs" / "protocols"


# --------------------------------------------------------------------- extension URIs


def test_every_extension_is_documented_by_a_knp_spec() -> None:
    assert set(EXT_SPEC) == set(Ext)
    for ext, spec in EXT_SPEC.items():
        doc = next(PROTOCOL_DOCS.glob(f"{spec.lower()}-*.md"), None)
        assert doc is not None, f"{ext} claims {spec}, which has no file in docs/protocols/"


def test_extension_uris_in_code_match_the_specs_that_declare_them() -> None:
    """ADR-0006: the URIs are a public commitment. Code and spec must not drift."""
    for ext, spec in EXT_SPEC.items():
        doc = next(PROTOCOL_DOCS.glob(f"{spec.lower()}-*.md"))
        assert ext.value in doc.read_text(encoding="utf-8"), (
            f"{doc.name} does not state its own extension URI {ext.value}"
        )


def test_every_documented_extension_uri_exists_in_code() -> None:
    """The reverse drift: a spec inventing a URI the code does not serve."""
    declared = {e.value for e in Ext}
    pattern = re.compile(r"https://kourob\.org/ext/[a-z]+/v\d+")
    for doc in PROTOCOL_DOCS.glob("*.md"):
        for found in pattern.findall(doc.read_text(encoding="utf-8")):
            assert found in declared, f"{doc.name} names {found}, which protocols.py lacks"


def test_metadata_keys_are_namespaced_by_the_extension_uri() -> None:
    assert key(Ext.SCOPE, "route_hints") == "https://kourob.org/ext/scope/v1/route_hints"


def test_activation_header_round_trips() -> None:
    header = activation_header(Ext.SCOPE, Ext.RECEIPT)
    assert parse_activation(header) == [Ext.SCOPE.value, Ext.RECEIPT.value]
    assert parse_activation("  ,, ") == []


# ------------------------------------------------------------------------ the envelope


def test_an_in_scope_answer_without_citations_is_not_grounded() -> None:
    """KNP-0 I1. This is the invariant the whole provenance story rests on."""
    answer = Answer(data={"x": 1}, rendered="x is 1", receipt_id="rcpt_1")
    assert not answer.is_grounded()


@pytest.mark.parametrize("result", [ScopeResult.REFERRAL, ScopeResult.REJECT])
def test_a_refusal_may_have_no_citations(result: ScopeResult) -> None:
    answer = Answer(data=None, rendered="not mine", receipt_id="rcpt_1", scope_result=result)
    assert answer.is_grounded()


def test_a_bridged_answer_must_still_cite() -> None:
    """KNP-1 section 5: citations are the upstream's event ids, not nothing."""
    answer = Answer(
        data={"x": 1}, rendered="x", receipt_id="rcpt_1", scope_result=ScopeResult.BRIDGE
    )
    assert not answer.is_grounded()


def test_refusal_reasons_are_not_collapsed() -> None:
    """KNP-1 section 6: re-route and retry are different caller behaviours."""
    assert RefusalReason.OUT_OF_SCOPE != RefusalReason.UNAVAILABLE
    assert len(set(RefusalReason)) == 6


# ---------------------------------------------------------------------- determinism


def test_only_t0_is_derived() -> None:
    """KNP-0 section 2 and ADR-0008: `derived` means a stranger can re-run it."""
    derived = [t for t, d in TIER_DETERMINISM.items() if d is Determinism.DERIVED]
    assert derived == [Tier.T0]


def test_every_tier_has_a_determinism_class() -> None:
    assert set(TIER_DETERMINISM) == set(Tier)


# -------------------------------------------------------------------------- outcomes


def test_reality_and_human_outcomes_outweigh_self_reported_ones() -> None:
    """ADR-0007: a caller grading its own answer is strategic."""
    assert SOURCE_WEIGHT[OutcomeSource.REALITY] > SOURCE_WEIGHT[OutcomeSource.CALLER]
    assert SOURCE_WEIGHT[OutcomeSource.HUMAN] > SOURCE_WEIGHT[OutcomeSource.DOWNSTREAM]


def test_unresolved_is_not_a_settlement() -> None:
    assert Verdict.UNRESOLVED in set(Verdict)


# ---------------------------------------------------------------------------- evolve


def test_a_cluster_nobody_settles_cannot_promote() -> None:
    """ADR-0007: unverifiable work does not get to be cheap."""
    unverifiable = ClusterStats(key="c", volume=5000, settle_rate=0.0, answer_entropy=1.0)
    assert unverifiable.is_function
    assert not unverifiable.can_promote


def test_a_cluster_with_varying_answers_is_not_a_function() -> None:
    assert not ClusterStats(key="c", volume=10, settle_rate=1.0, answer_entropy=1.4).is_function


def test_payback_gates_a_promotion() -> None:
    """KNP-5 section 4: a cluster about to go quiet is not worth distilling."""
    worth_it = Proposal(kind=ProposalKind.PROMOTE, payback_requests=400, expected_remaining=3400)
    not_worth_it = Proposal(
        kind=ProposalKind.PROMOTE, payback_requests=9100, expected_remaining=3400
    )
    assert worth_it.pays_back
    assert not not_worth_it.pays_back


def test_derived_share_may_not_fall() -> None:
    """KNP-5 section 1: cost may drop only if verifiability did not."""
    now = datetime.now(UTC)
    before = Objective(cost_per_settled_request=0.0067, derived_share=0.34, quality_multiplier=0.94)
    cheaper_but_opaque = Objective(
        cost_per_settled_request=0.0011, derived_share=0.19, quality_multiplier=0.94
    )
    report = EvolveReport(
        node="did:key:z6Mk",
        window_start=now,
        window_end=now,
        objective=cheaper_but_opaque,
        previous=before,
    )
    assert not report.constraints_held()
