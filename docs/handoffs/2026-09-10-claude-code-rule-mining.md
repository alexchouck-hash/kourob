# 2026-09-10 · claude-code · rule mining by exact replay

Task: `kb-24l`. The second item on the queue, and the one that turns a promotion proposal
into a cost curve.

## Done

### The miner — `src/kourob/loops/distill/mine.py`

`mine_rule(store, cluster, verdicts)` takes a cluster whose answers have always been a
function (`answer_entropy == 1.0`, settled), finds the one payload field the question's
subject equals on **every** settled request, builds a regex from the cluster's dominant
question frame and a SQL lookup on that field, and **replays** the candidate over every
settled request. `Candidate.promotable` is the ADR-0008 gate: `replay_exact_match == 1.0`
and `coverage >= 0.95`.

"Exact" compares **cited event sets** — what `derived` promises a stranger — because that is
checkable from the request log today. Comparing rendered text needs the log to keep it.

The output is the same YAML a hand-written rule is, run by the same T0 tier, with a
`mined:` block recording the replay and a `settles:` block so its answers can be settled.

### The loop — `src/kourob/loops/evolve.py`

- `_propose_promotions` now mines any function cluster straight to T0 from wherever it
  sits. Exact replay is a stronger gate than any tolerance rung; the no-skip rule exists to
  stop tolerance shortcuts, of which T0 has none. Declines say why: not mineable, not exact,
  or under coverage. The proposal carries `rule_yaml`, so a reviewer reads the rule rather
  than imagining it, and `payback_requests` is 0 — installing a rule costs nothing.
- `_propose_demotions` is the **one change evolve makes itself**: a T0 receipt with a
  `corrected` outcome renames its rule to `.yaml.disabled` in the same run and proposes the
  DEMOTE with `counter_examples`, the receipts, and its inverse (`enable`). It withdraws a
  privilege whose evidence stopped holding and it is trivially reversible.
- Promotion thresholds are overridable from `manifest.loops.evolve` (`n_rule`).

### Fixtures and evals

`testing.t3_answered_cell` disables the hand-written rule, ingests N notes, has a scripted
T3 answer "what is topic-N" citing the right note, and settles every answer `accepted` from
reality. `node_with_promoted_rule`, `correct_one_t0_answer`, `cluster_with_an_edge_case`
(twenty bindable questions and one that is not: coverage 0.952), `outcomes_for_tier`.

`evals/promotion_test.py` runs for real: a function of one event is mined and replayed
T3→T0 with exact 1.0 and coverage 1.0; one corrected outcome disables the rule in the same
run; partial coverage promotes and partial correctness does not; a sabotaged replay names
its miss. `tests/test_mining.py` covers the gate arithmetic, the subject, the frame pattern.

## Surprises

1. **`re` forbids the same group name twice.** A rule binding `subject` from several frames
   at once is not one regex. One frame per rule, minority frames uncovered — and the replay
   gate counts that honestly against coverage instead of papering over it.
2. **T3 receipts have no `settle_key`**, so `note_check` events cannot settle them. The
   fixture settles by `submit(source=REALITY)` directly. This is the limit KNP-2 §2.1
   already names; mining a rule with a `settles:` block is what fixes it going forward —
   the *mined* rule's answers do get settled by events.
3. **The suite is slow now** — ~4 minutes. `two_node_fixture` and `t3_answered_cell` each
   build several cells. Worth a session-scoped fixture cache before it gets worse.

## Not done

- **Nothing installs a promoted rule** — `tend` (`kb-2ff`). The fixture writes the YAML by
  hand to test demotion.
- **Multi-event joins and multi-frame rules.** v1 mines single-event lookups on one frame.
  A cluster that is a function of something v1 cannot see is declined with that reason.
- **Text replay.** The request log does not keep the rendered answer.
- **Claim 3** (no promoted rule is ever corrected over 30 replayed days) still needs T1 and
  `replay_synthetic_traffic`.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest evals/promotion_test.py -q
bd ready
```

Next: `bd show kb-2ff` — `kourob tend`, which is now the only thing between a mined rule
and a node that actually gets cheaper.
