# 2026-09-11 · claude-code · T1 and the measured cost curve

Task: `kb-ayo`. The headline number, measured for the first time — and the cost of measuring
it, found for the first time.

## Done

### T1, the student — `src/kourob/tiers/t1_student.py`

A nearest-settled-answer model. Every settled, accepted answer is an example: content
tokens, question frame, cited events, and the label the node's rule path gives the question
(`rule:<id>`, `t3`, `refuse`). A new question is matched by token overlap within the same
frame and answered from that example's events. No weights: a JSON file, deterministic,
explainable, `attested`. Cost is a JSON lookup, three orders below a frontier call.

- **Gold** is a store table written only by the gate (`kourob distill gold`), read only to
  score (`calibrate.py`). Training (`train.py`) joins requests with outcomes and never
  touches it. The rail holds by construction.
- **`T1Student.enable` refuses without gold.** The cascade constructs T1 only when the
  manifest says enabled, and only `enable` sets that. `tend` proposes rather than applies a
  T1 promotion on a node with no gold; applied, its inverse is `disable`, and `rollback`
  switches it off with the model file kept.
- **Calibration is per class**: the lowest bar at which every class the student is
  confident about hits the target. A silent student is scored as the cascade carrying on
  (`t3` in scope, `refuse` out), not as a refusal — the first scorer punished it for
  knowing its limits.
- **The ladder skips a disabled T2 with the stricter gate carried down.** T1 is never
  skipped: it is disabled until promoted to, which is what the promotion does.
- **T0 now costs a scan, not its price.** `cost_credits` on a T0 answer was `base_cost[T0]`
  — a price — and a rule that costs its price can never look cheaper than its price.

`tests/test_t1.py`: 14 tests. The student tracks the teacher within 2 points on the tennis
gold, per class; T0 still runs first; a paraphrase is answered at T1 without a model call.

### The cost curve — `evals/cost_curve.py`

`replay_synthetic_traffic`: thirty days, two hundred questions a day (70 % rule-bindable
lookups, 30 % paraphrases only a model answers), through the real serving path with a
scripted grounded model priced at the default token rate; every accepted answer settled that
day as `source: reality`; `tend` at A2 weekly; T1 off on day one and enabled by the
operator's move at the first weekly cycle.

**T0+T1 share on day 30 ≥ 80 % — measured, passes** (GOAL.md metric 2, 40 min 51 s).
**Day-1 cost over day-30 cost ≥ 5× — measured, passes** (metric 3, 48 min 38 s, run
concurrently with the suite). The eval asserts the ratio and does not print it; a follow-up
should log the day-by-day numbers so the shape of the curve is on record, not just the
verdict.

A third claim fell out of the same run: **KNP-5 §10 claim 3** — a T0 rule promoted by exact
replay was never corrected across thirty days of settled traffic. It had been `xfail` as
untested since the spec was written; it passed strictly the first time the replay existed,
and is now a `slow` eval alongside the other two.

Three earlier replays failed for reasons worth keeping:

1. **The caller ran out of free allowance on day one.** Every later request was refused for
   credit at no cost — T0+T1 share 0.00, the eval failed correctly. A month-long caller pays.
2. **Pricing was O(receipts).** Quality was recomputed from the whole ledger on every
   request. Now from the last evolve report, else a small file cache refreshed every two
   hundred receipts; a young node recomputes every time.
3. **The accounts table gained one Parquet part per paid request and was never folded.**
   Every price check read thousands of files. The store now compacts any table past 64
   parts on its own.

A profile of two hundred requests then found: `stats` opening every part's footer (fifty
thousand `ParquetFile` constructions), `_parts` re-globbing seven directories per query,
`Node.contracts` re-parsing every contract YAML per access, `load_rules` re-parsing rule
YAML per request. All four fixed.

**And it is still 40 minutes for one replay** — about 400 ms a request. The two replay
evals are marked `slow` and excluded from the default run (`-m 'not slow'`); run them on
purpose with `-m slow`. `kb-0sl` carries the remaining suspects: a `Node` is opened per
request so per-instance caches reset; T1 parses a growing `student.json` per request;
weekly `tend` re-labels every settled example and replays mined rules with one SQL per
settled request.

## Surprises

1. **The tokenizer dropped one-character tokens**, so "shot 1" and "shot 2" were the same
   question to the student. Found by a similarity test.
2. **The tennis cell had no declared exclusions**, so "who wins wimbledon" was `t3` to the
   teacher and the gold had no `refuse` class. A shot-charting cell does not predict
   winners; now it says so.
3. **Every replay failure was the eval working.** Three times it failed for a real reason
   that was not the one the assertion was about. The assertion messages carried the number
   that mattered each time.

## Not done

- **Replay performance** (`kb-0sl`) — the measurement is right and too expensive.
- **The reference UI** eval stays xfail; `examples/ui` does not exist.
- **A real T1**: the nearest-example student is honest at this scale and the tier interface
  is what a LoRA attaches to. Nothing here should be mistaken for one.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_t1.py -q                 # ~6 min: the fixture warms a student
uv run pytest evals/cost_curve.py -q -m slow      # ~40 min per replay, two replays
```
