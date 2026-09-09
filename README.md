# KouroB

KouroB is an open-source structure for building **nodes**: small, specialized, metered
units of knowledge and capability that other builders can create, connect, and chain into
products. A node owns a slice of the world (typed events, compiled knowledge, tools,
provenance), serves requests through standard ports (MCP, A2A, REST), and refuses or
refers anything outside its scope. Every request leaves a signed receipt, so provenance
and cost are traceable across chains of nodes. Frontier models *train* nodes; nodes then
*serve* far more cheaply than a frontier model would.

## One-command demo

```bash
pipx install kourob          # or: uv tool install kourob
kourob init demo && cd demo
kourob ingest fixtures/events.jsonl
kourob serve --mcp
```

Then attach an agent: `kourob attach claude-code`.

## What it is not

- **Not an agent.** KouroB is a node network. `ouroboros` is a heavily used name in the
  agent and blockchain worlds (razzant/ouroboros is a self-modifying agent; Cardano's
  networking stack is called Ouroboros). KouroB is neither.
- **Not a chat-memory product.** Not Mem0, Letta, or Hindsight. Memory here is an
  event-sourced, cited, versioned artifact in a git repo.
- **Not a smaller LLM.** A node is a compiled artifact of what an LLM figured out about
  one narrow job, plus the data that job needs.
- **Not a UI framework.** `examples/ui/` is a reference thin client, not a product.
- **Not a blockchain.** Credits are an internal ledger in v1. No money moves. See
  `docs/adr/0003-ledger-design.md`.

## Documentation

- `GOAL.md` — the one paragraph and the v1.0 metrics
- `AGENTS.md` — how agents work in this repo (read this first if you are an agent)
- `docs/brief/07-kourob-development.md` — the full design brief
- `docs/DEFAULTS.md` — decide-do-not-ask policy
- `docs/adr/` — architecture decision records

## License

Apache-2.0. See `LICENSE` and `docs/adr/0002-license-apache-2.0.md`.
