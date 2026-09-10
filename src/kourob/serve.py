"""Answering: run the cascade, build the envelope, write the receipt.

Brief reference: section 3.1 steps 4 to 7. Envelope: KNP-0 I1. Receipt: KNP-2.

This is the one place an answer is assembled, so it is the one place the invariants can be
enforced: no answer without a receipt, no in-scope answer without citations.
"""

from __future__ import annotations

import time

from kourob import events as ev
from kourob.ledger.chain import RECORD_RECEIPT
from kourob.node import Node
from kourob.request_log import RequestRecord, answer_shape, new_request_id, question_shape
from kourob.runner.run import Runner
from kourob.store.parquet_duckdb import ParquetDuckDBStore
from kourob.tiers.base import Request
from kourob.tiers.cascade import Cascade, CascadeResult
from kourob.tiers.t0_rules import T0Rules
from kourob.tiers.t3_frontier import T3Frontier
from kourob.types import Answer, RefusalReason, ScopeResult, Tier

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
    return Cascade(
        node.manifest,
        {
            Tier.T0: T0Rules(node.dir, store, base_cost=base[Tier.T0]),
            Tier.T3: T3Frontier(node.dir, store, runner, node.manifest),
        },
    )


def answer(
    node: Node, question: str, *, caller: str = "user:local", runner: Runner | None = None
) -> Answer:
    """Answer one question and receipt it. Never returns without a receipt id."""
    request = Request(question=question, caller=caller)
    started = time.perf_counter()
    run = build_cascade(node, runner=runner).run(request)
    latency_ms = (time.perf_counter() - started) * 1000

    if run.answered and run.result is not None:
        result = run.result
        receipt = _receipt(
            node,
            request,
            run,
            scope_result=ScopeResult.IN_SCOPE,
            response={"data": result.data, "rendered": result.rendered},
        )
        _log_request(node, request, run, receipt, latency_ms)
        return Answer(
            data=result.data,
            rendered=result.rendered,
            citations=result.citations,
            receipt_id=receipt["id"],
            scope_result=ScopeResult.IN_SCOPE,
            tier_used=result.tier,
            determinism=result.determinism,
        )

    tried = ", ".join(f"{a.tier.value}({a.confidence:.2f})" for a in run.attempts) or "no tier ran"
    rendered = (
        f"No tier cleared its confidence bar for this question. Tried: {tried}.\n"
        "This node holds no fact that answers it, and it will not guess."
    )
    receipt = _receipt(
        node,
        request,
        run,
        scope_result=ScopeResult.REJECT,
        response={"data": None, "rendered": rendered},
        reason=RefusalReason.OUT_OF_SCOPE,
    )
    _log_request(node, request, run, receipt, latency_ms)
    return Answer(
        data=None,
        rendered=rendered,
        citations=[],
        receipt_id=receipt["id"],
        scope_result=ScopeResult.REJECT,
        reason=RefusalReason.OUT_OF_SCOPE,
    )


def _log_request(
    node: Node, request: Request, run: CascadeResult, receipt: dict, latency_ms: float
) -> None:
    """Write the row the evolve loop reads (brief section 3.1 step 7).

    Every request, whatever happened to it. Refusals are the most informative rows in the
    log: they are where a node's declared scope and its real demand disagree.
    """
    result = run.result
    schemas = sorted(
        {
            str(row.get("schema_ref"))
            for cite in (result.citations if result else [])
            if (row := node.store.get("silver", cite))
        }
    )
    record = RequestRecord(
        id=new_request_id(),
        ts=ev.now().isoformat(),
        question=request.question,
        shape=question_shape(request.question),
        caller=request.caller,
        scope_result=str(receipt["scope_result"]),
        reason=receipt.get("reason"),
        decided_by=result.model_version if result else "refused",
        tier_used=result.tier.value if result else None,
        tiers_tried=[a.tier.value for a in run.attempts],
        determinism=result.determinism.value if result else None,
        schemas=schemas,
        tools=[],
        answer_shape=answer_shape(result.data if result else None),
        citations=list(result.citations) if result else [],
        citations_n=len(result.citations) if result else 0,
        latency_ms=latency_ms,
        cost_credits=run.total_cost,
        price_credits=float(receipt.get("price_credits") or 0.0),
        receipt_id=str(receipt["id"]),
        settle_key=receipt.get("settle_key"),
        request_hash=str(receipt["request_hash"]),
        response_hash=str(receipt["response_hash"]),
    )
    node.store.append("requests", [record.as_row()])


def _receipt(
    node: Node,
    request: Request,
    run: CascadeResult,
    *,
    scope_result: ScopeResult,
    response: dict,
    reason: RefusalReason | None = None,
) -> dict:
    """Hash the request and response; never store them (KNP-2 section 1)."""
    result = run.result
    price = node.manifest.pricing.base_cost.get(result.tier, 0.0) if result else 0.0
    return node.ledger.append(
        RECORD_RECEIPT,
        {
            "id": ev.new_id(ev.RECEIPT_PREFIX),
            "caller": request.caller,
            "request_hash": ev.sha256({"question": request.question}),
            "response_hash": ev.sha256(response),
            "scope_result": scope_result.value,
            "reason": reason.value if reason else None,
            "tier_used": result.tier.value if result else None,
            "determinism": result.determinism.value if result else None,
            "model_version": result.model_version if result else "none",
            "citations": list(result.citations) if result else [],
            "upstream": [],
            "hops": [*request.hops, node.did],
            "settle_key": result.settle_key if result else None,
            "cost_credits": run.total_cost,
            "price_credits": price,
            "ts": ev.now().isoformat(),
        },
    )


__all__ = ["answer", "build_cascade"]
