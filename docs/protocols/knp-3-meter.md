# KNP-3: Price quotes and credit settlement

Status: draft · Milestone: M4 · Extension URI: `https://kourob.org/ext/meter/v1`
Depends on: KNP-0, KNP-2 · Decides: ADR-0004

Credits are an internal ledger in v1. **No money moves.** This spec exists so that when it
does, nothing above it has to change.

## 1. Cost is measured, price is computed

**Cost** is what the request actually consumed, summed at the end of the cascade:

```
cost = Σ over tier attempts (tokens × unit_cost + compute_seconds × rate)
     + Σ over upstream calls (their price_credits)
```

Every term is observed, never estimated. The runner logs real token counts per attempt to
`logs/calls.parquet`; a tier attempt that failed its confidence bar still costs, and still
counts. A node that only charges for the tier that *succeeded* is hiding its cascade
inefficiency from itself, which is precisely the number the evolve loop needs.

**Price** is a function the node computes and publishes:

```
price = base_cost(tier_used) × (1 + demand_factor) × quality_multiplier

demand_factor = clamp(requests_last_window / capacity_window − 1, 0, max_surge)
```

## 2. Quoting

A caller asks before committing:

```
POST /a2a   A2A-Extensions: https://kourob.org/ext/meter/v1
{ "method": "GetQuote", "params": { "message": {...}, "hops": [...] } }
```

```json
{
  "quote_id": "qt_01JBQ9...",
  "scope_result": "in_scope",
  "expected_tier": "T1",
  "price_credits": 0.0006,
  "price_ceiling_credits": 0.021,
  "upstream": [],
  "expires": "2026-09-09T21:09:11Z",
  "balance_credits": 4.12,
  "free_allowance_remaining": 61
}
```

`expected_tier` is what the scope classifier and cache predict. `price_ceiling_credits` is
what it costs if the cascade falls all the way through to T3 — **a node MUST NOT charge
above the ceiling it quoted.** That is the whole point of quoting: the cascade's uncertainty
is the node's risk, not the caller's.

A bridge (KNP-1 §5) quotes both legs separately and its ceiling includes the upstream's
ceiling. If the caller cannot cover the total, the node refuses with
`reason: insufficient_credit` rather than starting work it cannot finish.

## 3. The quality multiplier is earned, not set

`quality_multiplier` is not a knob. It is computed from settled outcomes (KNP-2 §6) over a
trailing window:

```
quality_multiplier = clamp(accepted / (accepted + corrected + rejected), q_min, q_max)
```

Receipts still inside their `outcome_window` are excluded. Receipts past it with no outcome
count as `unresolved` and are excluded from the numerator but **included in the
denominator** — a node that cannot be checked drifts toward `q_min`.

This makes the economics honest in a way a self-declared quality score cannot: a node that
answers confidently and wrongly gets cheaper, not more expensive, and a node whose answers
nobody ever settles cannot charge a premium for them.

## 4. Settlement

v1: `ledger/accounts.parquet`, one row per counterparty, updated on receipt append. Every
caller gets `free_allowance` requests per window per the manifest. Balances are internal;
there is no transfer out.

Settlement is **post-paid against a quote**: the node answers, appends the receipt, and
debits `price_credits`, which is bounded by the quote's ceiling. Pre-payment (escrow) is
deliberately not built — it doubles the round trips to solve a problem that does not exist
between parties who share a set.

## 5. Where real money would attach

When it does, the hook is an HTTP 402 carrying the quote above, and a retry carrying proof
of payment — the x402 / L402 shape. Nothing in KNP-1, 2, or 4 changes: the receipt already
records `price_credits`, and a payment proof is one more field.

Deliberately not decided (ADR-0004 revisit clause): which settlement rail, whether the
facilitator is a set operator or a third party, and whether credits are ever
denominated in a real currency. Per brief §15, credits are internal in v1 and that is
intentional. Evaluate when three or more independent operators exist and one of them wants
paying.
