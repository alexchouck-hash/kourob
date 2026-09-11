# 2026-09-10 · claude-code · the MCP transport

Task: `kb-dj7`. GOAL.md metric 1 on the letter: an agent attaches and gets a cited answer.

## Done

- **`src/kourob/ports/mcp_server.py`** — the five tools over stdio with the official SDK
  (mcp 2.x, `MCPServer`). Each tool returns the envelope as structured content, so an agent
  gets `receipt_id` and `citations` as fields, not prose. The SDK import is lazy: the extra
  is optional and `import kourob` never needs it.
- **`kourob serve --mcp --node <cell>`** — blocks on stdio. `--a2a` / `--rest` still exit 2.
- **`kourob attach claude-code|cursor`** writes a project-scoped `.mcp.json` in the cell,
  idempotently; `attach codex` prints the TOML fragment. Attaching to a *node* is refused and
  pointed at `kourob connect`.
- **`tests/test_mcp_server.py`** spawns the real server process and speaks the real
  protocol: five tools listed, a cited receipted answer to "what is a bridge", a refusal
  that is still an envelope, and the attach config. Skips cleanly if the extra is absent.

## Surprises

1. **mcp 2.x renamed FastMCP to `MCPServer`** and moved it; the pyproject pin `mcp>=1.0`
   resolved to 2.2.0. The code targets 2.x; pinning `<2` would have been the wrong fix.

## Not done

- **A2A and REST** — still stubs. Nothing outside this machine can reach a cell.
- **Prompts and resources** over MCP — tools only. A `pages/` resource is the obvious M2
  addition once compile exists.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv sync --extra mcp --dev && uv run pytest tests/test_mcp_server.py -q
D=/tmp/demo && uv run kourob init $D && uv run kourob attach claude-code --node $D
```

Next: `kb-k60` — price function, quotes, accounts, meter report.
