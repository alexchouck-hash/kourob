"""The MCP transport: an agent attaches over stdio and gets the envelope.

Brief reference: section 12 M1, GOAL.md metric 1 - "a node answering over MCP with a
cited answer". This spawns the real server as a subprocess and speaks the real protocol to
it; nothing here touches the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from kourob.cli import app
from kourob.testing import node_with_events

pytest.importorskip("mcp", reason="the MCP SDK is an extra: uv sync --extra mcp")

pytestmark = pytest.mark.m1


def _call(cell: Path, calls: list[tuple[str, dict[str, Any]]]) -> tuple[list[str], list[dict]]:
    """Spawn the server, list its tools, run `calls`, return (tool names, results)."""
    import anyio
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "kourob.ports.mcp_server", str(cell)]
    )

    async def run() -> tuple[list[str], list[dict]]:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(t.name for t in (await session.list_tools()).tools)
            results = []
            for tool, args in calls:
                result = await session.call_tool(tool, args)
                structured = getattr(result, "structuredContent", None)
                if structured is None:
                    structured = json.loads(result.content[0].text)
                results.append(structured)
            return names, results

    return anyio.run(run)


def test_an_agent_lists_five_tools_and_gets_a_cited_answer(tmp_path: Path) -> None:
    cell = node_with_events(tmp_path, scope="the KouroB design, as notes")

    names, (answer, schemas) = _call(
        cell,
        [("query", {"question": "what is a bridge"}), ("list_schemas", {})],
    )

    assert names == ["get_page", "ingest", "list_schemas", "query", "submit_outcome"]
    assert answer["scope_result"] == "in_scope"
    assert answer["citations"] and answer["citations"][0].startswith("evt_")
    assert answer["receipt_id"].startswith("rcpt_")
    assert "bridge" in answer["rendered"].lower()
    assert {c["id"] for c in schemas["data"]} >= {"note.v1", "note_check.v1"}


def test_a_refusal_over_mcp_is_still_an_envelope(tmp_path: Path) -> None:
    cell = node_with_events(tmp_path)
    _, (refusal,) = _call(cell, [("query", {"question": "who wins wimbledon"})])
    assert refusal["scope_result"] == "reject"
    assert refusal["citations"] == []
    assert refusal["receipt_id"].startswith("rcpt_"), "a refusal is receipted like any answer"


def test_attach_writes_a_project_scoped_mcp_config(tmp_path: Path) -> None:
    cell = node_with_events(tmp_path)
    result = CliRunner().invoke(app, ["attach", "claude-code", "--node", str(cell)])
    assert result.exit_code == 0, result.output

    config = json.loads((cell / ".mcp.json").read_text(encoding="utf-8"))
    ((name, entry),) = config["mcpServers"].items()
    assert name == "kourob-cell"
    assert entry["command"] == "kourob"
    assert entry["args"][:2] == ["serve", "--mcp"]

    again = CliRunner().invoke(app, ["attach", "cursor", "--node", str(cell)])
    assert again.exit_code == 0
    assert len(json.loads((cell / ".mcp.json").read_text())["mcpServers"]) == 1, "idempotent"


def test_attach_refuses_a_path_and_points_at_connect(tmp_path: Path) -> None:
    cell = node_with_events(tmp_path)
    other = node_with_events(tmp_path, name="other")
    result = CliRunner().invoke(app, ["attach", str(other), "--node", str(cell)])
    assert result.exit_code == 1
    assert "kourob connect" in result.output
