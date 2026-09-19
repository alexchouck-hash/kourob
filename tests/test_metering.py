"""Price, quotes, accounts, and the meter report.

Brief reference: section 4.4 and 5.1. KNP-3.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob import serve
from kourob.cli import app
from kourob.ledger.accounts import Accounts
from kourob.ledger.meter import report
from kourob.ledger.pricing import Pricer, demand_factor, price_for
from kourob.testing import node_with_events, note_check
from kourob.types import RefusalReason, ScopeResult, Tier

pytestmark = pytest.mark.m4


@pytest.fixture
def cell(tmp_path: Path) -> Path:
    return node_with_events(tmp_path, scope="the KouroB design, as notes")


def _set(cell: Path, **pricing) -> None:
    node = node_mod.open_node(cell)
    for key, value in pricing.items():
        setattr(node.manifest.pricing, key, value)
    manifest_mod.save(cell, node.manifest)


# ------------------------------------------------------------------------- the function


def test_price_is_base_below_capacity_and_rises_monotonically_above_it() -> None:
    base = price_for(Tier.T3, requests_in_window=0, capacity_window=100, max_surge=3.0)
    assert base == 0.02
    loads = [50, 100, 150, 200, 400, 100_000]
    prices = [
        price_for(Tier.T3, requests_in_window=n, capacity_window=100, max_surge=3.0) for n in loads
    ]
    assert prices == sorted(prices)
    assert prices[0] == prices[1] == base, "no surge at or below capacity"
    assert prices[-1] == pytest.approx(base * 4.0), "capped at 1 + max_surge"


def test_quality_scales_the_price_and_is_clamped() -> None:
    kw = {"requests_in_window": 0, "capacity_window": 100, "max_surge": 3.0}
    assert price_for(Tier.T0, quality_multiplier=1.5, **kw) == pytest.approx(0.00015)
    assert price_for(Tier.T0, quality_multiplier=9.0, **kw) == pytest.approx(0.00015), "q_max"
    assert price_for(Tier.T0, quality_multiplier=0.0, **kw) == pytest.approx(0.00005), "q_min"


def test_demand_factor_edges() -> None:
    assert demand_factor(0, 0, 3.0) == 0.0
    assert demand_factor(300, 100, 3.0) == 2.0
    assert demand_factor(10_000, 100, 3.0) == 3.0


# ----------------------------------------------------------------------------- quotes


def test_a_quote_predicts_t0_for_a_rule_bound_question(cell: Path) -> None:
    quote = Pricer(node_mod.open_node(cell)).quote("what is a bridge", "user:x")
    assert quote.scope_result is ScopeResult.IN_SCOPE
    assert quote.expected_tier is Tier.T0
    assert quote.price_credits <= quote.price_ceiling_credits
    assert quote.free_allowance_remaining == 100
    assert quote.affordable()


def test_a_quote_predicts_the_dearest_tier_when_no_rule_binds(cell: Path) -> None:
    # A question no rule's frame matches. ("explain everything" *binds* the starter rule and
    # is predicted T0; whether the SQL then finds rows is the cascade's business, not the
    # quote's - the quote predicts, and the ceiling is what protects the caller.)
    quote = Pricer(node_mod.open_node(cell)).quote("how many aces did B hit", "user:x")
    assert quote.expected_tier is Tier.T3
    assert quote.price_credits == quote.price_ceiling_credits


def test_the_ceiling_is_never_exceeded(cell: Path) -> None:
    """KNP-3 section 2: the cascade's uncertainty is the node's risk, not the caller's."""
    _set(cell, capacity_window=1, max_surge=3.0)  # everything is over capacity
    node = node_mod.open_node(cell)
    quote = Pricer(node).quote("what is a bridge", "user:x")

    answer = serve.answer(node_mod.open_node(cell), "what is a bridge", caller="user:x")
    receipt = next(
        r for r in node_mod.open_node(cell).ledger.records() if r["id"] == answer.receipt_id
    )

    assert 0 < receipt["price_credits"] <= quote.price_ceiling_credits


def test_price_reflects_earned_quality(cell: Path) -> None:
    node = node_mod.open_node(cell)
    unmeasured = Pricer(node).price(Tier.T0)

    serve.answer(node, "what is a bridge")
    node_mod.open_node(cell).ingest(note_check(cell, "bridge", "accepted"))

    earned = Pricer(node_mod.open_node(cell)).price(Tier.T0)
    assert earned > unmeasured, "an unmeasured node prices at q_min; an accepted answer lifts it"


# --------------------------------------------------------------------------- allowance


def test_a_caller_over_its_allowance_with_no_balance_is_refused(cell: Path) -> None:
    _set(cell, free_allowance=2)
    for _ in range(2):
        assert serve.answer(node_mod.open_node(cell), "what is a bridge", caller="user:p").tier_used

    third = serve.answer(node_mod.open_node(cell), "what is a bridge", caller="user:p")

    assert third.scope_result is ScopeResult.REJECT
    assert third.reason is RefusalReason.INSUFFICIENT_CREDIT
    assert "No work was started" in third.rendered
    assert third.receipt_id.startswith("rcpt_"), "the refusal is receipted"


def test_a_funded_caller_is_debited_once_the_allowance_is_spent(cell: Path) -> None:
    _set(cell, free_allowance=1)
    node = node_mod.open_node(cell)
    Accounts(node.store).credit("user:rich", 1.0, note="top up")

    serve.answer(node_mod.open_node(cell), "what is a bridge", caller="user:rich")  # free
    assert Accounts(node_mod.open_node(cell).store).balance("user:rich") == 1.0

    paid = serve.answer(node_mod.open_node(cell), "what is a cell", caller="user:rich")
    receipt = next(
        r for r in node_mod.open_node(cell).ledger.records() if r["id"] == paid.receipt_id
    )

    balance = Accounts(node_mod.open_node(cell).store).balance("user:rich")
    assert balance == pytest.approx(1.0 - receipt["price_credits"])
    assert receipt["price_credits"] > 0


def test_accounts_are_append_only_and_summed_on_read(cell: Path) -> None:
    accounts = Accounts(node_mod.open_node(cell).store)
    accounts.grant("did:key:z6MkMe", 10.0)
    accounts.debit("did:key:z6MkMe", 0.25, receipt_id="rcpt_1")
    accounts.debit("did:key:z6MkMe", 0.0, receipt_id="rcpt_2")  # nothing to charge
    assert accounts.balance("did:key:z6MkMe") == pytest.approx(9.75)
    assert accounts.statement() == {"did:key:z6MkMe": pytest.approx(9.75)}
    assert node_mod.open_node(cell).store.stats("accounts")["rows"] == 2


# ------------------------------------------------------------------------------ report


def test_the_meter_report_adds_up(cell: Path) -> None:
    for q in ("what is a bridge", "what is a cell", "who wins wimbledon"):
        serve.answer(node_mod.open_node(cell), q, caller="user:a")
    serve.answer(node_mod.open_node(cell), "what is a receipt", caller="user:b")

    out = report(cell, "30d")

    assert out.requests == 4 and out.answered == 3
    assert out.revenue == pytest.approx(sum(row["revenue"] for row in out.by_tier.values()))
    assert out.cost == pytest.approx(sum(row["cost"] for row in out.by_tier.values()))
    assert out.margin == pytest.approx(out.revenue - out.cost)
    assert out.top_callers[0][0] == "user:a" and out.top_callers[0][1] == 3
    assert "T0" in out.by_tier and "-" in out.by_tier, "refusals are counted, at no tier"
    assert out.state in ("growing", "stable", "failing")


def test_meter_commands_run(cell: Path) -> None:
    serve.answer(node_mod.open_node(cell), "what is a bridge")
    runner = CliRunner()
    assert "margin" in runner.invoke(app, ["meter", "report", "--node", str(cell)]).output
    price = runner.invoke(app, ["meter", "price", "--node", str(cell)])
    assert price.exit_code == 0 and "demand factor" in price.output and "T0" in price.output
