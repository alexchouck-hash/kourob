# 2026-09-22 · claude-code · settle_key from citations (kb-7db)

This is the first step of the auditable-self-improvement direction in
`docs/ideas/2026-09-22-self-improving-pivot.md`, which Alex approved in session with
wedge A (dogfood on this machine) to start.

Grepped adr/experiments/spikes for `settle`: ADR-0007 (outcomes; no training on unlabelled
T3 output) and ADR-0008 (exact replay). Neither blocks this change. KNP-2 §2.1 recorded the
null T3 key as a limit. It is now superseded by ADR-0010.

## Done

- `ledger/outcomes.settle_key_from_citations(contracts, store, citations)`. It reads the
  cited silver events. For each one whose contract settles, it computes the key from that
  contract's `settle_key` fields. It returns the key only when exactly one distinct subject
  results. Otherwise it returns null.
- `serve._receipt` uses it when the tier result has no key of its own. T0's bound key always
  wins. Bridged answers cite events outside local silver and stay null.
- `tests/test_settle_key_citations.py` has 6 tests:
  - a T3 answer citing one note carries its key
  - a later `note_check` settles it from reality as `corrected`
  - an answer citing two subjects stays null
  - two notes on one subject still settle
  - no settleable citation gives null
  - T0's key is unchanged
- ADR-0010, KNP-2 §2.1, STATUS weakness #5, the ADR index, and a stale docstring in
  `tests/test_outcomes.py` are updated.
- Lint on the uncommitted 2026-09-19 Gemini files is fixed (ruff autofix and format, plus
  a missing `from typing import Any` in `scope.py`). Those files are still **uncommitted**
  and are not part of this commit.

## Not done

- Shadow teacher, the next task. It judges answers that have no subject by receipt id.
- No measurement yet of the share of model answers left null. That needs real traffic
  (wedge A).

## Surprises

- T3 accepts only citations it retrieved. A question worded "bridges and receipts" (plural)
  missed keyword retrieval for both notes, so T3 declined. The test uses singular wording.
  This is another data point for STATUS weakness #7, keyword retrieval.

## Open questions

- Gemini's Jev endpoint (`api.typesafe.ai/v1/systemone`) is still unverified against live
  docs. Their work sits uncommitted on this branch.

## Resume

```bash
cd c:/Users/houck/kourob
uv run pytest tests/test_settle_key_citations.py tests/test_outcomes.py -q
uv run pytest -q -m "not slow"
bd show kb-7db
```
