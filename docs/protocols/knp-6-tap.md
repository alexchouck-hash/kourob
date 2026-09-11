# KNP-6: The tap — subscribing to a cell's data flow

Status: draft · Milestone: M3–M5 · Extension URI: `https://kourob.org/ext/tap/v1`
Depends on: KNP-0, KNP-2

A UI is just another caller. This spec is what makes that true in practice: a stable, typed,
receipted way to watch a cell's flow, so anyone can build their own view without knowing
anything about the cell's insides.

## 1. Why a separate spec

Request/response is enough for a question. It is not enough for a dashboard, a board that
refreshes three times a day, an alerting rule, or a person who wants to watch what a cell is
doing. Those need a **stream**, and a stream needs its own contract: what is emitted, in
what shape, with what guarantees on ordering and replay.

Without one, every UI reaches into a cell's files, and the membrane (KNP-8 §2.2) is gone.
`predictions.json` published as a static artefact is exactly this shape today: it works, and
it is an undeclared, unversioned, unmetered dependency that nothing can refuse or price.

## 2. Three taps

| Tap | Emits | Typical consumer |
|---|---|---|
| `events` | events as they pass the gate, typed by `schema_ref` | another cell, a warehouse, a live view |
| `answers` | answer envelopes as they are served, with `receipt_id` | a dashboard, an audit view |
| `changes` | `node_change.v1` events from `tend` (KNP-7 §4.1) | a set operator watching autonomous cells |

Each is a separately subscribable topic with separate scope and price. A UI that only wants
the board does not subscribe to the change feed and does not pay for it.

## 3. Transport

CloudEvents envelope over SSE, with webhooks as the delivery alternative. The CloudEvents
`data` is the ODCS-typed payload; `datacontenttype` names the schema id and version.

```
GET /tap/answers?since=rcpt_01JBQ7...&schema=match_prediction.v1
Accept: text/event-stream
A2A-Extensions: https://kourob.org/ext/tap/v1
```

```
event: kourob.answer
id: rcpt_01JBQ8...
data: {"specversion":"1.0","type":"org.kourob.answer","source":"did:key:z6MkPred...",
       "datacontenttype":"application/vnd.kourob.match_prediction.v1+json",
       "id":"rcpt_01JBQ8...","time":"2026-09-09T21:04:11Z",
       "data":{"data":{...},"rendered":"...","citations":["evt_..."],"receipt_id":"rcpt_01JBQ8..."}}
```

`since` takes a receipt or event id and replays forward from it, which is what makes a tap
recoverable: a UI that was offline resumes exactly where it stopped, and the ids are ULIDs
so ordering is total and monotonic.

## 4. Guarantees, and what is not guaranteed

**Guaranteed**: at-least-once delivery; total order per cell; every item carries an id that
`kourob trace` resolves; replay from any id still inside retention; the payload validates
against the named schema version.

**Not guaranteed**: exactly-once (consumers dedupe on id — ids are stable, so this is
trivial); cross-cell ordering (there is no global clock and there will not be one);
retention beyond the cell's declared window for `events`. Receipts are kept forever, so the
`answers` tap can always be replayed even when the events behind it have aged out — the
answer stays traceable through its receipt even after the raw stream is gone.

## 5. Building a UI against a tap

The contract a UI depends on is exactly the four contact-surface items in KNP-8 §4 plus the
tap topics. That is the whole coupling. In particular a UI must not:

- read the cell's files, database, or Parquet directly;
- depend on tier mix, model version, or which rule answered — all of that is in the receipt
  for display, none of it is stable;
- re-render `rendered` into a claim without carrying its `citations` and `receipt_id`.

The reference client in `examples/ui/` exists to prove the constraint from brief §12 M5:
*renders a node's answer from REST with no node-specific code.* If it ever needs to know
about tennis, that is the bug.

A person who wants a different view builds a different client against the same tap. That is
the intended end state: **many custom UIs over one metered, receipted, typed flow**, and the
cell neither knows nor cares how many there are.

## 6. Metering a subscription

A tap is metered per item delivered, at `base_cost(T0)` — a tap replays what was already
computed and paid for, so it prices as a read, not a re-answer. `free_allowance` applies.
A subscriber that falls `max_lag` behind is disconnected and must resume with `since`, which
bounds a cell's obligation to a slow consumer.
