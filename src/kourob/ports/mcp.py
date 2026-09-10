"""MCP port: query, ingest, get_page, list_schemas.

Brief reference: section 12 (M1). Envelope: KNP-0 I1.

Ports are thin. Everything here is translation: an MCP tool call in, an `Answer` out. The
logic lives in `serve`, `gate` and `node`, and if this file starts making decisions that is
the bug.

In M1 `get_page` returns the raw event list, because pages arrive with the compile loop in
M2. It still returns a full envelope, so callers do not have to change when it does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob import serve
from kourob.ledger.chain import RECORD_RECEIPT
from kourob.node import Node, open_node
from kourob.types import Answer, Determinism, RefusalReason, ScopeResult

__milestone__ = "M1"

TOOLS = ("query", "ingest", "get_page", "list_schemas", "submit_outcome")


def handle(node_dir: Path | str | Node, tool: str, args: dict[str, Any]) -> Answer:
    """Dispatch one MCP tool call. Always returns a full envelope, including on refusal."""
    node = node_dir if isinstance(node_dir, Node) else open_node(node_dir)
    if tool == "query":
        return serve.answer(
            node, str(args.get("question", "")), caller=args.get("caller", "user:mcp")
        )
    if tool == "ingest":
        return _ingest(node, args)
    if tool == "get_page":
        return _get_page(node, args)
    if tool == "list_schemas":
        return _list_schemas(node)
    if tool == "submit_outcome":
        return _submit_outcome(node, args)
    return _refuse(node, f"no such tool {tool!r}; this node offers {', '.join(TOOLS)}")


def _ingest(node: Node, args: dict[str, Any]) -> Answer:
    lines = args.get("lines") or ([args["path"]] and Path(args["path"]).read_text().splitlines())
    report = node.gate.ingest_lines(list(lines), source=str(args.get("source", "mcp")))
    data = {
        "accepted": report.accepted,
        "rejected": report.rejected,
        "reasons": report.reasons,
        "event_ids": report.event_ids,
    }
    rendered = f"accepted {report.accepted}, quarantined {report.rejected}" + "".join(
        f"\n  {count:>4}  {step}" for step, count in sorted(report.reasons.items())
    )
    return _envelope(node, data, rendered, report.event_ids)


def _get_page(node: Node, args: dict[str, Any]) -> Answer:
    """M1: the events themselves. M2 replaces this with a compiled, cited page."""
    topic = args.get("page") or args.get("topic")
    if node.store.stats("silver")["rows"] == 0:
        return _refuse(node, "this node holds no events yet")
    rows = node.store.scan("silver")
    if topic and topic != "index":
        rows = [r for r in rows if (r.get("payload") or {}).get("topic") == topic]
    if not rows:
        return _refuse(node, f"no events for page {topic!r}")
    rendered = "\n".join(f"- {(r.get('payload') or {})} [{r['id']}]" for r in rows[:50])
    return _envelope(node, rows, rendered, [r["id"] for r in rows])


def _list_schemas(node: Node) -> Answer:
    contracts = node.contracts
    data = [
        {"id": c.id, "version": c.version, "name": c.name, "fields": len(c.fields)}
        for c in contracts.values()
    ]
    rendered = "\n".join(f"- `{c['id']}` v{c['version']} — {c['fields']} fields" for c in data)
    # Introspection, not a claim about the world: the node is reciting its own
    # declaration, which is signed in its agent card. There is no event to cite.
    return _envelope(
        node, data, rendered or "this node declares no contracts", [], Determinism.DECLARED
    )


def _submit_outcome(node: Node, args: dict[str, Any]) -> Answer:
    """KNP-2 section 6.3. The submission surface for `ext/outcome/v1`.

    A submitter who is not the receipt's caller is recorded at the lowest weight, never
    refused: a third party noticing an error is useful even when it cannot be trusted.
    """
    from kourob.ledger.outcome import OutcomeSource, Verdict
    from kourob.ledger.outcomes import OutcomeError, submit

    try:
        outcome = submit(
            node.ledger,
            str(args["receipt_id"]),
            verdict=Verdict(str(args.get("verdict", "accepted"))),
            source=OutcomeSource(str(args.get("source", "caller"))),
            evidence=list(args.get("evidence") or []),
            by=args.get("by"),
            note=args.get("note"),
        )
    except (KeyError, OutcomeError, ValueError) as exc:
        return _refuse(node, f"outcome not recorded: {exc}")

    data = outcome.model_dump(mode="json")
    rendered = (
        f"recorded {outcome.verdict.value} on {outcome.about} "
        f"from {outcome.source.value} (weight {outcome.weight})"
    )
    # The outcome is a fact this node now holds, and its evidence is what supports it.
    return _envelope(node, data, rendered, list(outcome.evidence) or [], Determinism.DECLARED)


def _envelope(
    node: Node,
    data: Any,
    rendered: str,
    citations: list[str],
    determinism: Determinism | None = None,
) -> Answer:
    receipt = _receipt(node, ScopeResult.IN_SCOPE, {"data": data}, citations, determinism)
    return Answer(
        data=data,
        rendered=rendered,
        citations=citations,
        receipt_id=receipt["id"],
        scope_result=ScopeResult.IN_SCOPE,
        determinism=determinism,
    )


def _refuse(node: Node, why: str) -> Answer:
    receipt = _receipt(node, ScopeResult.REJECT, {"data": None, "rendered": why}, [], None)
    return Answer(
        data=None,
        rendered=why,
        citations=[],
        receipt_id=receipt["id"],
        scope_result=ScopeResult.REJECT,
        reason=RefusalReason.OUT_OF_SCOPE,
    )


def _receipt(
    node: Node,
    scope_result: ScopeResult,
    response: dict[str, Any],
    citations: list[str],
    determinism: Determinism | None = None,
) -> dict[str, Any]:
    """No answer leaves this port without one (KNP-0 I1)."""
    return node.ledger.append(
        RECORD_RECEIPT,
        {
            "id": ev.new_id(ev.RECEIPT_PREFIX),
            "caller": "user:mcp",
            "request_hash": ev.sha256({"port": "mcp"}),
            "response_hash": ev.sha256(response),
            "scope_result": scope_result.value,
            "reason": None if scope_result is ScopeResult.IN_SCOPE else "out_of_scope",
            "tier_used": None,
            "determinism": determinism.value if determinism else None,
            "model_version": "port:mcp",
            "citations": citations,
            "upstream": [],
            "hops": [node.did],
            "cost_credits": 0.0,
            "price_credits": 0.0,
            "ts": ev.now().isoformat(),
        },
    )


__all__ = ["TOOLS", "handle"]
