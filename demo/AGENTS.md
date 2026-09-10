# AGENTS.md

You are attached to a KouroB node. Read `GOAL.md` first: it is the scope, and the scope is
the contract.

## What this node is

One folder, one process, one manifest (`kourob.yaml`). It owns a slice of the world as
typed events, compiles those events into cited pages, serves them through its ports, and
records a signed receipt for every request.

## Rules

1. **Answer from events.** Every claim you make on this node's behalf cites an event id.
   No citation, no claim.
2. **Refuse or refer what is out of scope.** Do not guess outside `GOAL.md`. Check
   `routes.parquet` (`kourob routes list`) for a node that does own it.
3. **The gate is the only writer.** Never write `data/silver/` or `data/gold/` yourself.
   Push through `kourob ingest`.
4. **Every model call goes through the runner** so it is costed. `kourob run`.
5. **Every answer is `{data, rendered, citations, receipt_id}`.**

## Where to look

| Question | File |
|---|---|
| What does this node answer? | `GOAL.md`, `kourob scope show` |
| What is true here? | `pages/index.md`, then `kourob query` |
| Why is it true? | `kourob trace <receipt_id>` |
| What shape is the data? | `schemas/*.odcs.yaml`, `kourob schema list` |
| What can I do here? | `tools/`, `kourob tools list` |
| What did this cost? | `kourob meter report` |

## Session end

Write `docs/handoffs/YYYY-MM-DD-<agent>-<task>.md`: done, not done, surprises, open
questions, exact resume commands.
