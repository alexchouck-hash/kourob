# 2026-09-22 · claude-code · the shadow teacher (kb-csy)

This is the second step of the self-improvement direction
(`docs/ideas/2026-09-22-self-improving-pivot.md`), after settle keys from citations
(kb-7db, ADR-0010, pushed as `8a26015`).

Grepped adr/experiments/spikes for `teacher`, `agreement`, `outcome`. ADR-0007 option B
rejects tier agreement as a label. The design was changed to comply (see Decisions).

## Done

- `loops/shadow.py`: `run_shadow(node_dir, runner=, budget_credits=, now=)`.
  - It audits unsettled in-scope T0/T1/T2 answers with citations.
  - Sampling is per cluster at `max(0.05, 1/(1+agreements since last dispute))`, with a
    draw fixed by receipt id.
  - T3 re-answers with `purpose="shadow"`. Citation overlap decides the result: overlap is
    agree, disjoint is dispute, and a decline or low confidence is abstain.
  - Audits go to a new logical table `shadow` (`logs/shadow`).
- A dispute is a `rejected` outcome with the new `OutcomeSource.TEACHER` (weight 0) and the
  teacher's citations as evidence. Agreement writes no outcome.
- `ledger.outcomes.settling_outcomes` leaves teacher outcomes out. Everything that counts
  settlement reads through it: `settlement_status`, reality's "already settled" check,
  evolve's verdicts and cluster settle rates, and T1 training.
- evolve declines promotion for any cluster with an open dispute. A later settling
  outcome on the same receipt closes the dispute.
- An unreachable teacher records nothing, so those answers stay owed. Before this fix, the
  smoke test on a machine with no local model marked answers audited as "abstain".
- CLI: `kourob loop run shadow [--budget]`. The budget now defaults to the manifest's.
  The template manifest has `shadow: nightly, 0.5 credits`.
- `T3Frontier(purpose=...)`.
- 13 tests in `tests/test_shadow.py`. The sampling test pins `_draw` so it is exact.
- ADR-0011, KNP-2 §6.1 (the `teacher` row), the ADR index, STATUS, and the pivot doc are
  updated.

## Decisions made without asking

- **Agreement does not settle.** In chat I told Alex "if T3 agrees, the answer counts as
  settled". That is ADR-0007 option B, which is already rejected. Rather than contradict
  an accepted ADR, the teacher only disputes. ADR-0011 records it.
- Verdict for a dispute is `rejected`, not `corrected`. `corrected` needs evidence of what
  was true, and the teacher's opinion is not that.
- The comparator is citation overlap. The node stores answer hashes, not text, so
  comparing content was not available (ADR-0011 option C).

## Not done

- Nothing has run against a real model yet. This machine has no local model on :11434, so
  `kourob loop run shadow` reports the teacher unreachable. Wedge A (real traffic on this
  machine) needs either a local Ollama model or a configured vendor adapter.
- There is no T4 queue for disputes.
- The labeled-fraction metric proposed for GOAL.md is not computed or reported yet.

## Surprises

- Smoke-testing the CLI found both bugs fixed above: the budget override and the
  unreachable-teacher case. The tests alone had not.
- Heredoc `\n` mangling bit again (see memory). Fixed with the Edit tool.

## Resume

```bash
cd c:/Users/houck/kourob
uv run pytest tests/test_shadow.py tests/test_settle_key_citations.py -q
uv run pytest -q -m "not slow"
kourob loop run shadow --node <cell>   # needs a reachable T3
```
