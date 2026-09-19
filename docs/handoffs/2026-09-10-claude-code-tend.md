# 2026-09-10 · claude-code · kourob tend

Task: `kb-2ff`. The third item on the queue. A node can now change itself, within limits,
and undo it.

## Done

### `src/kourob/loops/tend.py`

    ingest -> evolve -> decide -> apply | propose -> report

`decide` asks three questions per proposal, in order, and any "no" turns an apply into a
propose: within the autonomy level? within budget? **is there a recorded inverse?** The
third does the real work — a change with no inverse is never auto-applied at any level. A
split and any scope change are proposals at every level.

An applied change is a `node_change.v1` event **pushed through the gate** like any other
fact, carrying its inverse. `kourob rollback <evt>` is a lookup, not a reconstruction, and
records a `rollback` change pointing at what it undid. Nothing in the apply path deletes: a
demoted rule is renamed `.yaml.disabled`, a shed schema keeps its data.

Halt conditions (ledger fails to verify, quality below floor once something has settled,
settle rate below floor once twenty receipts exist, two consecutive rollbacks) stop the
cycle, apply nothing, and **demote one autonomy level** — recorded as an `autonomy` change
with its inverse. Graduation is **suggested, never set**: a node cannot promote itself.

`kourob tend --autonomy-max A2 [--dry-run]` and `kourob rollback <evt>` are wired.

### Proven

At A2, `tend` installs the rule evolve mined and the node answers from it on the next
request; at A0 the same rule is proposed and nothing changes; `--autonomy-max` caps the
manifest; dry-run decides but applies nothing; rollback restores the prior state and the
node stops answering at T0; a correction after a promotion records the demotion with its
inverse; a tampered ledger halts and demotes A2→A1; A0 cannot demote further; two
rollbacks halt; graduation is suggested after the window and the manifest is untouched.

## Surprises

1. **The Store double-encoded JSON columns handed in as text.** `tamper_for_test`
   pre-serialised list columns, `_encode` serialised them again, `_decode` unwrapped once,
   and `Outcome` refused to validate the ledger the helper had just tampered with — a
   different failure from the one the tests wanted. Both ends fixed.
2. **`node_change.v1` put the template at its own schema ceiling.** A cell's change log is
   infrastructure, not world; `INFRASTRUCTURE_SCHEMAS` is exempt from `max_schemas`.
3. **A brand-new node would halt on quality.** `quality_multiplier` starts at `q_min`
   below `q_floor` with nothing settled. Halts now need evidence to fire on.

## Not done

- **Budget is nominal.** Every change costs 0 today; the budget path is exercised only
  by a synthetic cost. It becomes real when retraining (T1) has a price.
- **`tune` changes (A1)** — confidence bars, cache TTLs — have no proposals yet.
- **Compile, lint, reflect** are still stubs, so `tend` runs ingest and evolve only.
- **Graduation is computed from `tend` reports only**, not from the objective trend.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_tend.py -q
bd ready
```

Next on the queue: `kb-dj7` (MCP stdio server), `kb-k60` (metering).
