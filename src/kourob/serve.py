"""Answering: scope check, cascade, referral or bridge, envelope, receipt.

Brief reference: section 3.1 steps 2 to 7, section 3.2. Envelope: KNP-0 I1. Receipt: KNP-2.
Scope, referral and bridge: KNP-1. Route learning: KNP-9 section 3.

This is the one place an answer is assembled, so it is the one place the invariants can be
enforced: no answer without a receipt, no in-scope answer without citations, and no request
answered that the node has already seen on its way here.
"""

from __future__ import annotations

import time
from typing import Any

from kourob import events as ev
from kourob import scope as scope_mod
from kourob.ledger.accounts import Accounts
from kourob.ledger.chain import RECORD_RECEIPT
from kourob.ledger.pricing import Pricer
from kourob.node import Node
from kourob.ports.local import UnreachableNeighbourError, resolve
from kourob.protocols import Ext, key
from kourob.request_log import RequestRecord, answer_shape, new_request_id, question_shape
from kourob.routes import SOURCE_BRIDGE, RouteTable
from kourob.runner.run import Runner
from kourob.store.parquet_duckdb import ParquetDuckDBStore
from kourob.tiers.base import Request, TierResult
from kourob.tiers.cascade import Cascade, CascadeResult
from kourob.tiers.t0_rules import T0Rules
from kourob.tiers.t3_frontier import T3Frontier
from kourob.types import Answer, RefusalReason, RouteHint, ScopeResult, Tier

__milestone__ = "M1"


def build_cascade(node: Node, *, runner: Runner | None = None) -> Cascade:
    """T0 and T3. T1, T2 and T4 attach here as they land, and nothing else changes.

    A caller may pass its own `runner` — that is how a test scripts the model without any
    part of the serving path knowing it is being tested (DEFAULTS.md).
    """
    store = node.store
    if not isinstance(store, ParquetDuckDBStore):  # pragma: no cover - one backend in v1
        raise TypeError("v1 serves from the Parquet backend")
    base = node.manifest.pricing.base_cost
    runner = runner or Runner(node.manifest, store=store)
    handlers: dict[Tier, Any] = {
        Tier.T0: T0Rules(node.dir, store, base_cost=base[Tier.T0]),
        Tier.T3: T3Frontier(node.dir, store, runner, node.manifest),
    }
    if node.manifest.tier_enabled(Tier.T1):
        # Only constructed when enabled, and `enable` refuses without gold - so a T1 in
        # the cascade is a T1 that was checked against something other than its teacher.
        from kourob.tiers.t1_student import T1Student

        handlers[Tier.T1] = T1Student(node.dir, store)
    return Cascade(node.manifest, handlers)


def answer(
    node: Node,
    question: str,
    *,
    caller: str = "user:local",
    hops: list[str] | None = None,
    runner: Runner | None = None,
) -> Answer:
    """Answer one question and receipt it. Never returns without a receipt id.

    In order (brief section 3.1): scope check, then the cascade, then — only if the cascade
    found nothing — a second look at the route table. A referral may become a bridge if the
    manifest allows it and this caller has not used up its introductions.
    """
    request = Request(question=question, caller=caller, hops=list(hops or []))
    routes = RouteTable(node.store, node.manifest.prune)
    started = time.perf_counter()

    pricer = Pricer(node)
    if not pricer.quote(question, caller, hops=request.hops).affordable():
        # KNP-3 section 2: refuse rather than start work the caller cannot pay for. Checked
        # against the *ceiling*, because the cascade's uncertainty is the node's risk.
        return _refuse(
            node, request, RefusalReason.INSUFFICIENT_CREDIT, started, decided_by="rule:allowance"
        )

    decision = scope_mod.check(node.manifest, routes, question, own_did=node.did, hops=request.hops)
    if decision.result is ScopeResult.REJECT:
        return _refuse(
            node,
            request,
            decision.reason or RefusalReason.OUT_OF_SCOPE,
            started,
            decided_by=decision.decided_by,
        )
    if decision.result is ScopeResult.REFERRAL:
        return _refer_or_bridge(node, request, routes, decision, started)

    run = build_cascade(node, runner=runner).run(request)
    if run.answered and run.result is not None:
        return _answered(node, request, run, started)

    miss = scope_mod.after_miss(routes, question)
    if miss.result is ScopeResult.REFERRAL:
        return _refer_or_bridge(node, request, routes, miss, started, run=run)
    return _refuse(
        node, request, RefusalReason.OUT_OF_SCOPE, started, run=run, decided_by=miss.decided_by
    )


# ---------------------------------------------------------------------------- answered


def _answered(node: Node, request: Request, run: CascadeResult, started: float) -> Answer:
    result = run.result
    assert result is not None
    receipt = _receipt(
        node,
        request,
        scope_result=ScopeResult.IN_SCOPE,
        response={"data": result.data, "rendered": result.rendered},
        result=result,
        cost=run.total_cost,
        price=_price(node, request, result.tier),
    )
    _charge(node, request, receipt)
    _log(node, request, receipt, started, run=run, decided_by=result.model_version)
    return Answer(
        data=result.data,
        rendered=result.rendered,
        citations=result.citations,
        receipt_id=receipt["id"],
        scope_result=ScopeResult.IN_SCOPE,
        tier_used=result.tier,
        determinism=result.determinism,
    )


# ---------------------------------------------------------------- referral and bridge


def _bridges_used(node: Node, caller: str, neighbour: str) -> int:
    """How many introductions this caller has already had to this neighbour.

    Counted from the request log rather than a separate table: a bridge is a request, and
    the log already records who asked and where it went (KNP-1 section 5.1).
    """
    if node.store.stats("requests")["rows"] == 0:
        return 0
    rows = node.store.query(
        "SELECT count(*) AS n FROM requests WHERE scope_result = 'bridge' "
        "AND caller = $caller AND decided_by = $decided",
        {"caller": caller, "decided": f"bridge:{neighbour}"},
    ).to_pylist()
    return int(rows[0]["n"] or 0)


def _refer_or_bridge(
    node: Node,
    request: Request,
    routes: RouteTable,
    decision: scope_mod.ScopeDecision,
    started: float,
    *,
    run: CascadeResult | None = None,
) -> Answer:
    route = decision.route
    assert route is not None
    policy = node.manifest.bridge
    used = _bridges_used(node, request.caller, route.node)

    if policy.enabled and used < policy.bridge_limit:
        bridged = _bridge(node, request, routes, decision, started, used, run=run)
        if bridged is not None:
            return bridged

    hints = decision.hints
    rendered = (
        f"Out of scope. {node.manifest.scope.summary}\n"
        f"Try {route.name or route.node} ({route.summary or 'no summary'})."
    )
    if used >= policy.bridge_limit:
        rendered += (
            f"\nThis caller has used its {policy.bridge_limit} introductions to that node; "
            "go direct."
        )
    receipt = _receipt(
        node,
        request,
        scope_result=ScopeResult.REFERRAL,
        response={"data": None, "rendered": rendered},
        result=None,
        cost=run.total_cost if run else 0.0,
        price=0.0,
    )
    _log(node, request, receipt, started, run=run, decided_by=decision.decided_by)
    return Answer(
        data=None,
        rendered=rendered,
        citations=[],
        receipt_id=receipt["id"],
        scope_result=ScopeResult.REFERRAL,
        route_hints=hints,
        metadata=_scope_metadata(ScopeResult.REFERRAL, decision, hints, used, policy.bridge_limit),
    )


def _bridge(
    node: Node,
    request: Request,
    routes: RouteTable,
    decision: scope_mod.ScopeDecision,
    started: float,
    used: int,
    *,
    run: CascadeResult | None,
) -> Answer | None:
    """Ask the neighbour on the caller's behalf, once, and hand back the route.

    Returns None when the neighbour cannot be reached or refuses, in which case the caller
    gets a plain referral and the route is weakened (KNP-9 section 3).
    """
    route = decision.route
    assert route is not None
    try:
        neighbour = resolve(route)
    except UnreachableNeighbourError:
        routes.reinforce(route.node, success=False)
        return None

    upstream = neighbour.ask(request.question, caller=node.did, hops=[*request.hops, node.did])
    upstream_latency = (time.perf_counter() - started) * 1000
    if upstream.scope_result not in (ScopeResult.IN_SCOPE, ScopeResult.BRIDGE):
        routes.reinforce(route.node, success=False)
        return None

    routes.reinforce(
        route.node, success=True, latency_ms=upstream_latency, evidence=upstream.receipt_id
    )
    hint = scope_mod.hint_for(routes.get(route.node) or route)
    hint.evidence = upstream.receipt_id
    hints = [hint]

    price = node.manifest.pricing.base_cost.get(Tier.T0, 0.0)
    receipt = _receipt(
        node,
        request,
        scope_result=ScopeResult.BRIDGE,
        response={"data": upstream.data, "rendered": upstream.rendered},
        result=None,
        cost=run.total_cost if run else 0.0,
        price=price,
        upstream=[upstream.receipt_id],
        citations=list(upstream.citations),
        tier=upstream.tier_used,
        determinism=upstream.determinism,
        model_version=f"bridge:{route.node}",
    )
    _log(
        node,
        request,
        receipt,
        started,
        run=run,
        decided_by=f"bridge:{route.node}",
        citations=list(upstream.citations),
    )
    return Answer(
        data=upstream.data,
        rendered=upstream.rendered,
        citations=list(upstream.citations),
        receipt_id=receipt["id"],
        scope_result=ScopeResult.BRIDGE,
        tier_used=upstream.tier_used,
        determinism=upstream.determinism,
        route_hints=hints,
        metadata=_scope_metadata(
            ScopeResult.BRIDGE, decision, hints, used + 1, node.manifest.bridge.bridge_limit
        ),
    )


def _scope_metadata(
    result: ScopeResult,
    decision: scope_mod.ScopeDecision,
    hints: list[RouteHint],
    used: int,
    limit: int,
) -> dict[str, Any]:
    """Extension data under `ext/scope/v1`, per ADR-0006 and KNP-1 section 4."""
    return {
        key(Ext.SCOPE, "scope_result"): result.value,
        key(Ext.SCOPE, "decided_by"): decision.decided_by,
        key(Ext.SCOPE, "matched_exclude"): decision.matched_exclude,
        key(Ext.SCOPE, "route_hints"): [h.model_dump(mode="json") for h in hints],
        key(Ext.SCOPE, "bridge"): {"used": used, "limit": limit, "resets": None},
    }


# ----------------------------------------------------------------------------- refuse


def _refuse(
    node: Node,
    request: Request,
    reason: RefusalReason,
    started: float,
    *,
    run: CascadeResult | None = None,
    decided_by: str = "rule:default",
) -> Answer:
    if reason is RefusalReason.LOOP:
        rendered = "Refused: this request has already passed through this node (hop list)."
    elif reason is RefusalReason.HOPS_EXHAUSTED:
        rendered = f"Refused: hop budget of {node.manifest.scope.max_hops} exhausted."
    elif reason is RefusalReason.INSUFFICIENT_CREDIT:
        rendered = (
            "Refused: this caller has used its free allowance and its balance does not cover "
            "the price ceiling. Ask for a quote, or top up. No work was started."
        )
    elif run is not None:
        tried = ", ".join(f"{a.tier.value}({a.confidence:.2f})" for a in run.attempts)
        rendered = (
            f"No tier cleared its confidence bar for this question. Tried: {tried or 'none'}.\n"
            "This node holds no fact that answers it, knows no node that does, and will not "
            "guess."
        )
    else:
        rendered = f"Out of scope, and no node is known for it. {node.manifest.scope.summary}"
    receipt = _receipt(
        node,
        request,
        scope_result=ScopeResult.REJECT,
        response={"data": None, "rendered": rendered},
        result=None,
        cost=run.total_cost if run else 0.0,
        price=0.0,
        reason=reason,
    )
    _log(node, request, receipt, started, run=run, decided_by=decided_by)
    return Answer(
        data=None,
        rendered=rendered,
        citations=[],
        receipt_id=receipt["id"],
        scope_result=ScopeResult.REJECT,
        reason=reason,
        metadata={
            key(Ext.SCOPE, "scope_result"): ScopeResult.REJECT.value,
            key(Ext.SCOPE, "reason"): reason.value,
            key(Ext.SCOPE, "decided_by"): decided_by,
        },
    )


# ------------------------------------------------------------------------ metering


def _price(node: Node, request: Request, tier: Tier) -> float:
    """KNP-3: computed, never above the ceiling a caller could have been quoted.

    The ceiling is recomputed here rather than carried on the request, because the request
    log is what the pricer reads and it has not changed since the quote: same window, same
    quality. A node MUST NOT charge above what it quoted, and capping at the ceiling is how
    that promise survives a cascade that fell further than expected.
    """
    pricer = Pricer(node)
    return round(min(pricer.price(tier), pricer.ceiling()), 9)


def _charge(node: Node, request: Request, receipt: dict[str, Any]) -> None:
    """Debit the caller once its free allowance is spent. Post-paid against the receipt."""
    price = float(receipt.get("price_credits") or 0.0)
    if price <= 0:
        return
    if Pricer(node).free_remaining(request.caller) > 0:
        return
    Accounts(node.store).debit(request.caller, price, receipt_id=str(receipt["id"]))


# ------------------------------------------------------------------ receipt and log


def _receipt(
    node: Node,
    request: Request,
    *,
    scope_result: ScopeResult,
    response: dict[str, Any],
    result: TierResult | None,
    cost: float,
    price: float,
    reason: RefusalReason | None = None,
    upstream: list[str] | None = None,
    citations: list[str] | None = None,
    tier: Tier | None = None,
    determinism: Any = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Hash the request and response; never store them (KNP-2 section 1)."""
    tier = tier or (result.tier if result else None)
    determinism = determinism or (result.determinism if result else None)
    return node.ledger.append(
        RECORD_RECEIPT,
        {
            "id": ev.new_id(ev.RECEIPT_PREFIX),
            "caller": request.caller,
            "request_hash": ev.sha256({"question": request.question}),
            "response_hash": ev.sha256(response),
            "scope_result": scope_result.value,
            "reason": reason.value if reason else None,
            "tier_used": tier.value if tier else None,
            "determinism": determinism.value if determinism else None,
            "model_version": model_version or (result.model_version if result else "none"),
            "citations": citations
            if citations is not None
            else (list(result.citations) if result else []),
            "upstream": list(upstream or []),
            "hops": [*request.hops, node.did],
            "settle_key": result.settle_key if result else None,
            "cost_credits": cost,
            "price_credits": price,
            "ts": ev.now().isoformat(),
        },
    )


def _log(
    node: Node,
    request: Request,
    receipt: dict[str, Any],
    started: float,
    *,
    run: CascadeResult | None,
    decided_by: str,
    citations: list[str] | None = None,
) -> None:
    """Write the row the evolve loop reads (brief section 3.1 step 7).

    Every request, whatever happened to it. Refusals and referrals are the most informative
    rows in the log: they are where a node's declared scope and its real demand disagree.
    """
    result = run.result if run else None
    cited = citations if citations is not None else (list(result.citations) if result else [])
    schemas = sorted(
        {str(row.get("schema_ref")) for c in cited if (row := node.store.get("silver", c))}
    )
    record = RequestRecord(
        id=new_request_id(),
        ts=ev.now().isoformat(),
        question=request.question,
        shape=question_shape(request.question),
        caller=request.caller,
        scope_result=str(receipt["scope_result"]),
        reason=receipt.get("reason"),
        decided_by=decided_by,
        tier_used=receipt.get("tier_used"),
        tiers_tried=[a.tier.value for a in run.attempts] if run else [],
        determinism=receipt.get("determinism"),
        schemas=schemas,
        tools=[],
        answer_shape=answer_shape(result.data if result else None),
        citations=cited,
        citations_n=len(cited),
        latency_ms=(time.perf_counter() - started) * 1000,
        cost_credits=float(receipt.get("cost_credits") or 0.0),
        price_credits=float(receipt.get("price_credits") or 0.0),
        receipt_id=str(receipt["id"]),
        settle_key=receipt.get("settle_key"),
        request_hash=str(receipt["request_hash"]),
        response_hash=str(receipt["response_hash"]),
    )
    node.store.append("requests", [record.as_row()])


__all__ = ["SOURCE_BRIDGE", "answer", "build_cascade"]
