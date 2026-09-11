"""The MCP transport: the five tools over stdio, so an agent can attach.

Brief reference: section 12 (M1), GOAL.md metric 1. Envelope: KNP-0 I1.

`ports/mcp.py` is the handler and knows nothing about transports; this file is the
transport and knows nothing about answering. Every tool returns the same envelope —
`{data, rendered, citations, receipt_id}` plus the scope fields — as a structured result,
so an agent gets a receipt id it can act on rather than prose it has to parse.

Run it with `kourob serve --mcp --node <cell>`, or directly:
`python -m kourob.ports.mcp_server <cell>`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from kourob.ports.mcp import TOOLS, handle

__milestone__ = "M1"


def _envelope(node_dir: Path, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return handle(node_dir, tool, args).model_dump(mode="json")


def build_server(node_dir: Path | str) -> Any:
    """An MCPServer exposing this cell's tools. Imported lazily: the SDK is an extra."""
    from mcp.server.mcpserver import MCPServer

    from kourob.node import open_node

    node_dir = Path(node_dir)
    node = open_node(node_dir)
    server = MCPServer(
        f"kourob:{node.manifest.identity.name}",
        instructions=(
            f"{node.manifest.scope.summary}\n\n"
            "Every result is an envelope: data, rendered, citations (event ids), receipt_id. "
            "Cite the receipt_id when you use an answer. A scope_result of referral or "
            "reject means this cell does not own the question; route_hints say who might."
        ),
    )

    @server.tool(name="query", description="Ask this cell a question through its tier cascade.")
    def query(question: str, caller: str = "user:mcp") -> dict[str, Any]:
        return _envelope(node_dir, "query", {"question": question, "caller": caller})

    @server.tool(name="ingest", description="Push JSONL lines through the gate into silver.")
    def ingest(lines: list[str], source: str = "mcp") -> dict[str, Any]:
        return _envelope(node_dir, "ingest", {"lines": lines, "source": source})

    @server.tool(
        name="get_page", description="Read a compiled page, or the raw events for a topic."
    )
    def get_page(page: str = "index") -> dict[str, Any]:
        return _envelope(node_dir, "get_page", {"page": page})

    @server.tool(name="list_schemas", description="The contracts this cell declares.")
    def list_schemas() -> dict[str, Any]:
        return _envelope(node_dir, "list_schemas", {})

    @server.tool(
        name="submit_outcome",
        description="Say whether an answer held up: accepted, corrected (with evidence), rejected.",
    )
    def submit_outcome(
        receipt_id: str,
        verdict: str = "accepted",
        evidence: list[str] | None = None,
        note: str | None = None,
        by: str | None = None,
    ) -> dict[str, Any]:
        return _envelope(
            node_dir,
            "submit_outcome",
            {
                "receipt_id": receipt_id,
                "verdict": verdict,
                "evidence": evidence or [],
                "note": note,
                "by": by,
            },
        )

    assert set(TOOLS) == {"query", "ingest", "get_page", "list_schemas", "submit_outcome"}
    return server


def serve_stdio(node_dir: Path | str) -> None:
    """Block, serving over stdio, until the client disconnects."""
    build_server(node_dir).run("stdio")


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    serve_stdio(args[0] if args else ".")


if __name__ == "__main__":  # pragma: no cover - exercised by spawning it
    main()


__all__ = ["build_server", "main", "serve_stdio"]
