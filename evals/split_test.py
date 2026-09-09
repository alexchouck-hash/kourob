"""M4 acceptance: a bimodal request distribution produces a split proposal.

Brief section 12, M4 and section 5.2. A split is proposed when demand_factor has exceeded
`split_threshold` for `split_window` **and** the request distribution has at least two
clusters above `min_cluster_share` touching mostly disjoint schemas or tools. Both
conditions, because either one alone produces thrash (brief section 15).

Imports of not-yet-existing modules live inside the test bodies on purpose: a module-level
import would fail collection instead of producing an honest xfail.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.m4, pytest.mark.eval]

M4 = "M4 not implemented"


@pytest.mark.xfail(reason=M4)
def test_bimodal_demand_proposes_a_split_with_evidence(tmp_path) -> None:
    from kourob.testing import synthetic_request_log

    from kourob.loops.evolve import evolve

    node = synthetic_request_log(
        tmp_path,
        clusters={"shot.v1": 0.55, "serve_stats.v1": 0.45},
        days=21,
        demand_factor=1.4,
    )

    report = evolve(node)

    (proposal,) = [p for p in report.proposals if p.kind == "split"]
    assert {c.schema_ref for c in proposal.clusters} == {"shot.v1", "serve_stats.v1"}
    assert proposal.child_manifest is not None
    assert proposal.parent_scope_after != proposal.parent_scope_before
    assert proposal.referral_rule is not None
    assert proposal.evidence, "a split PR without evidence cannot be reviewed"


@pytest.mark.xfail(reason=M4)
def test_noisy_unimodal_demand_does_not_split(tmp_path) -> None:
    """Hysteresis: one busy week on one cluster is not a split."""
    from kourob.testing import synthetic_request_log

    from kourob.loops.evolve import evolve

    node = synthetic_request_log(
        tmp_path, clusters={"shot.v1": 0.97, "serve_stats.v1": 0.03}, days=3, demand_factor=2.0
    )

    assert not [p for p in evolve(node).proposals if p.kind == "split"]


@pytest.mark.xfail(reason=M4)
def test_price_rises_with_demand_and_returns_to_base(tmp_path) -> None:
    """Brief section 12, M4: monotonic in demand above capacity, back to base below it."""
    from kourob.ledger.pricing import price_for
    from kourob.types import Tier

    base = price_for(Tier.T0, requests_in_window=0, capacity_window=1000, max_surge=3.0)
    loads = [500, 1000, 1500, 2000, 4000]
    prices = [
        price_for(Tier.T0, requests_in_window=n, capacity_window=1000, max_surge=3.0) for n in loads
    ]

    assert prices == sorted(prices), f"price not monotonic in demand: {prices}"
    assert prices[0] == base, "price must not surge below capacity"
    assert prices[-1] <= base * 4.0, "max_surge not respected"
    assert price_for(Tier.T0, requests_in_window=10, capacity_window=1000, max_surge=3.0) == base


@pytest.mark.xfail(reason=M4)
def test_merkle_root_verifies_and_a_tampered_receipt_breaks_it(tmp_path) -> None:
    from kourob.testing import node_with_receipts

    from kourob.ledger.merkle import root_for, verify_against_registry
    from kourob.ledger.verify import tamper_for_test

    node, registry = node_with_receipts(tmp_path, count=32)

    assert verify_against_registry(node, registry)
    before = root_for(node)

    tamper_for_test(node, index=7, field="cost_credits", value=0.0)

    assert root_for(node) != before
    assert not verify_against_registry(node, registry)
