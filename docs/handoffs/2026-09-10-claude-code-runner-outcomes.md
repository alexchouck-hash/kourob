# 2026-09-10 · claude-code · runner, T3, and outcomes

Task: `kb-6om` (runner and local adapter), `kb-458` (T3 and cascade), `kb-p4q` (outcome
records and the submission port). All three closed.

## Done

### Runner — `src/kourob/runner/`

One entry point for every model call. Prices from the token counts an adapter **reports**;
an adapter that cannot count sets `tokens_estimated`, so a cost curve built on estimates is
distinguishable from one built on measurements. A failed call is logged **before** it is
re-raised.

The local adapter is both the real ollama/vLLM client and the scripted mock every test uses
— one class on purpose, so a test exercises the same logging and pricing path production
runs. An unscripted call raises rather than returning something plausible.

Token rates live in the manifest (`pricing.token_rates`), resolved model → adapter →
`default`, with separate prompt and completion rates because a blended one hides where the
money went.

### T3 — `src/kourob/tiers/t3_frontier.py`

Retrieves from the node's own events by keyword overlap (no vector store, per brief §10),
asks the model to answer only from them, then **checks every citation it gets back**:

- all citations fabricated → the tier **declines**. Emitting it would launder a guess into
  the provenance graph, which KNP-2 §5 names as the worst failure the protocol can have;
- some real, some fabricated → answers on the real ones and **halves confidence**;
- no events matched → declines without spending a call.

### Outcomes — `src/kourob/ledger/outcomes.py`

Appended to the same chain, judging a receipt without ever editing it. Receipts carry a
hashed `settle_key` naming what an answer was about, so an arriving fact finds the answers
it settles without either side learning the other's subject.

`Node.ingest()` runs the gate and then lets the new facts settle old answers. The template
ships the pair that demonstrates it: `note.v1` declares `settles_against: note_check.v1`,
and the `note-lookup` rule declares what its answers are about.

`unresolved` is **computed, never written** — appending a record to say nothing happened
would manufacture evidence out of its own absence. A node nobody checks drifts to `q_min`.

New CLI: `kourob outcome submit | list | status`. New MCP tool: `submit_outcome`.
`kourob doctor` now reports settlement, and `kourob trace` shows an answer and its
correction from one receipt id.

**99 passed, 15 xfailed.** CI green on Linux.

## Surprises

1. **A test found a real chain bug.** Records were ordered by id, and ids are
   `<prefix>_<ULID>` — so `outc_` sorted before `rcpt_` and `prev` broke the moment a node
   recorded its first outcome. The chain now carries an explicit `seq`. Unsigned, because
   reordering breaks `prev` and `prev` is the integrity mechanism.
2. **Receipts and outcomes share one Parquet table**, so a receipt read back after an
   outcome exists carries null columns belonging to the other record kind. That is storage,
   not content: `signed_view` is what a record *is*.
3. **`records()` on an empty ledger failed** for the same reason the gate did — an empty
   view has only an `id` column. Both now ask `stats` first. Worth a helper.

## Not done

- **T1, T2, T4.** The cascade is T0 and T3.
- **Real vendor adapters.** `openai`, `anthropic`, `gemini`, `claude_code`, `codex` are
  named and raise "not implemented yet" rather than being silently missing.
- **A settlement comparator.** A contract says *how* to judge (`settle_verdict_field`) or
  says nothing and the receipts stay unresolved. Probabilistic answers — a prediction node's
  Brier score — need a domain comparator, which is `kb-id9`'s real work.
- **T3 answers have no `settle_key`.** A free-text question has no subject the node can
  name, so those receipts are never settled. A real limit, documented in KNP-2 §2.1.

## Open questions

1. **What settles a probabilistic answer?** "Alcaraz 0.77" and Alcaraz wins is not
   `accepted` — it is a Brier contribution. Either `Verdict` grows a scored variant, or
   scoring lives outside the ledger and only its verdict lands in it. Decide before
   `kb-id9`.
2. **Keyword retrieval will stop scaling.** Fine for a narrow cell; brief §10 says Cognee
   when grep stops working. The trigger should be a measurement, not a feeling.
3. Everything still open from the previous handoffs: `kourob.org`, the regex-vs-classifier
   question for mined rules, and branch protection.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest -q
D=/tmp/demo && uv run kourob init $D && uv run kourob ingest $D/fixtures/events.jsonl --node $D
uv run kourob query "what is a bridge" --node $D
uv run kourob outcome status --node $D
bd ready
```

Next: `bd show kb-dvm` (demand clustering) is now unblocked and is the last thing between
here and a real evolve loop.
