# 2026-09-10 · claude-code · assessment, queue, and connect

Task: assess against GOAL.md, build the queue, work the top of it. `kb-9gv` closed.

## Assessment

`docs/STATUS.md` — new, rewritten-not-appended, goal-by-goal. Short form: create-a-node is
met; connect was **not started** and is now met on disk; cheaper is half (no rule mining);
better is met in mechanism; traced is met for one node; metered is half. Three of six
metrics met, two unmeasurable until rule mining exists.

## The queue

In Beads, ordered by what moves the one sentence rather than by milestone number. Created
`kb-9gv` connect, `kb-dj7` MCP server, `kb-2ff` tend, `kb-k60` metering, `kb-afx`
compile/lint, `kb-ayo` T1 + cost curve, `kb-2ha` entropy-per-event-set bug, `kb-rag` short
cluster ids. `bd human kb-id9` for the probabilistic-settlement question.

## Connect — done on the local transport

A node called another node for the first time. What exists now:

- **`routes.py`** — `Route`, `RouteTable`: connect, lookup by the neighbour's declared
  words, Hebbian `reinforce` (α 0.3 up, β 0.5 down), `decay`, `learn` from route hints.
  Append-only rows, latest wins.
- **`scope.py`** — `check` runs before any tier: loop and hop budget first, then declared
  exclusions → referral (or reject when `refer_to` is null), else in scope. `after_miss`
  gives the route table a second look only when the cascade found nothing.
- **`ports/local.py`** — the `Neighbour` contract and its first implementation, a path. A
  URL endpoint is refused rather than guessed at.
- **`serve.py`** — rewritten: scope check → cascade → referral or bridge. A bridge asks
  the neighbour with `caller = this did` and `hops + [this did]`, chains `upstream`,
  carries the neighbour's citations, reinforces the route, and returns a hint whose
  `evidence` is the upstream receipt. Introductions are counted from the request log.
  Extension data rides under `ext/scope/v1` per ADR-0006.
- **`node.connect`**, **`trace`** following `upstream` into the neighbour's ledger,
  **`kourob connect | disconnect | routes list | scope check | scope show`**.
- **`testing.two_node_fixture`** — kourob-node excludes tennis and names tennis-node; a
  caller knows only kourob-node.

`evals/router_test.py` passes on the real API: first call bridges with a route hint, the
caller's table then points at tennis-node, the second call is referred, the direct call
works, a hop list containing the node is refused, the hop budget is enforced, `trace`
shows both nodes and both receipts and the cited events, both chains still verify, and a
successful bridge strengthens the route.

## Surprises

1. **None of it needed a server.** Two directories exercised every protocol from KNP-1 on.
   That ordering is now written into KNP-1 §6.1 as deliberate.
2. **`trace` had to grow a notion of reachable ledgers.** An upstream receipt is in the
   neighbour's chain, signed with the neighbour's key. The route table is what knows where
   that chain is.

## Not done

- **A2A card and HTTP** (`kb-imt`) — transport, not mechanism.
- **T1 scope classifier** — rules only; `decided_by` records which, so evolve can mine it.
- **Route pruning is not called by anything** — `decay` exists; `prune` is a stub loop.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest -q
uv run kourob init /tmp/a && uv run kourob init /tmp/b --scope "tennis shot events"
uv run kourob connect /tmp/b --node /tmp/a && uv run kourob routes list --node /tmp/a
bd ready
```

Next: `bd show kb-24l` — rule mining by exact replay.
