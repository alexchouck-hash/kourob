# 2026-09-10 · claude-code · metering

Task: `kb-k60`. The unmet half of "metered along the whole chain".

## Done

- **`ledger/pricing.py`** — `price_for` implements brief §5.1 exactly:
  `base × (1 + demand_factor) × quality`, demand zero below capacity and capped at
  `max_surge`, quality clamped to `[q_min, q_max]`. `Pricer` reads demand from the request
  log over `pricing.window` and quality from settled outcomes. `Pricer.quote` scope-checks
  without running a tier, predicts the tier (T0 if a rule binds, else the dearest enabled),
  and promises a **ceiling** — the price at the dearest enabled tier.
- **`ledger/accounts.py`** — append-only movements, balance summed on read; `debit`,
  `credit`, `grant`, `statement`.
- **`serve.py`** — refuses `insufficient_credit` **before any work** when the caller's free
  allowance is spent and its balance cannot cover the ceiling; prices every in-scope receipt
  with the pricer, **capped at the ceiling**; debits post-paid once the allowance is gone.
- **`ledger/meter.py`** and **`kourob meter report | price`** — revenue, cost, margin,
  by tier, top callers, balances; the current demand factor, quality, ceiling, per-tier
  price.
- The M4 price eval (`evals/split_test.py`) passes for real; `tests/test_metering.py`
  proves the ceiling is never exceeded, the allowance refusal, the post-paid debit, and
  that an accepted outcome lifts the price.

## Not done

- **A bridge quotes one leg.** KNP-3 §2 says both, with the ceiling including the
  upstream's. The bridge path still prices at `base_cost[T0]` flat.
- **No GetQuote over a port.** `Pricer.quote` exists; nothing exposes it over MCP or A2A
  yet — a `quote` tool is a five-line addition once a caller wants it.
- **The bootstrap grant is a manifest number nothing spends.** It becomes real when tend's
  budget is real, i.e. when retraining costs credits.
- **ADR-0004** is still owed; KNP-3 and this code are its draft.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_metering.py -q
D=/tmp/demo && uv run kourob init $D && uv run kourob ingest $D/fixtures/events.jsonl --node $D
uv run kourob query "what is a bridge" --node $D && uv run kourob meter report --node $D
```

Next on the queue: `kb-id9` (predict-node receipts — needs your call on probabilistic
settlement), `kb-afx` (compile and lint), `kb-imt` (A2A card and HTTP).
