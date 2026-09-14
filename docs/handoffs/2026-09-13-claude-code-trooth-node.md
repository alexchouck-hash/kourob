# 2026-09-13 · claude-code · trooth-node, the first integration, and a human tap

Tasks: `kb-6hh` (the example), `kb-0sl` (replay performance, part one). The ask was an
example node on the public site, fed from Trooth, watched from a common open-source
dashboard.

## Done

### The Trooth in-port — `src/kourob/ports/trooth.py`

Trooth's signed envelopes become `observation.v1` events and its published scorecards
become `scorecard.v1` events. `kourob ingest --from-trooth` takes a file, a tree, or the
public site URL (reads `scorecards/manifest.json`, then one card per source). `fetch_envelope`
is written against `POST /fetch` for when the API is public; it is not today (`api.trooth.io`
does not resolve), so envelopes come from files.

- The payload is kept whole; the provenance is lifted beside it (decision 89).
- `untrusted_text` is not re-admitted; the event says how many strings were dropped (90).
- `ts` is the source timestamp, not the fetch time (91).

### The example — `examples/trooth-node/`

`build.py` lays the cell down from `kourob init`, swaps in the two committed contracts and
two T0 rules, and pushes the fixtures (one NWS envelope from Trooth's schema examples, the
five scorecards Trooth published on 2026-09-11). `tests/test_trooth_node.py` builds it the
same way: 12 tests, including the CLI path and the dashboard rendered headless.

```
kourob query "latest observation at KJFK"   →  T0 (derived), one citation, the source URL,
                                               lag and content hash on the answer
kourob query "how fresh is open-meteo"       →  T0, the scorecard's p50/p95/completeness
```

### The dashboard — `examples/trooth-node/dashboard.py`

Streamlit (`uv sync --extra ui`). Observations with provenance, scorecards with two bar
charts, serving by tier and cost per request by day, chain verification, last receipts, and
an Ask box that goes through `serve.answer`. Generic by construction: `open_node` and the
Store API only; no Parquet path, no node-specific code (92). Verified in the browser
against the built cell and in CI with `streamlit.testing.v1.AppTest`.

### The public site

A page for Trooth's site, `src/pages/examples/kourob-node.astro`, with an "Examples" nav
entry and a footer link, on branch `examples/kourob-node` of `alexchouck-hash/trooth-site`
as a PR. **Not deployed**: the site deploys by `npm run deploy` from a human's machine, and
publishing is the operator's call.

### Replay performance, part one (`kb-0sl`, still open)

Profiled 200 requests: 320 ms each → 91 ms. DuckDB's failed pandas import per query (93),
`count(*)` after every append, every changed view rebuilt per query, a fresh `Ledger` per
`node.ledger` access, three `Pricer`s per answer, the student and quality file parsed per
request, and compaction at 64 parts on a filesystem where a file open costs a millisecond.
The acceptance bar is a five-minute replay; at 91 ms a 6,000-request replay is ~9 minutes
before `tend`. Next suspects: T3 `retrieve` scans all of silver per call; `tend` re-labels
every settled example weekly; DuckDB per-statement overhead (~5 ms) × 4 statements per
answer — a single in-memory table appended per request and flushed per N would remove most
of it, at the cost of ADR-0001's "one part per append" audit property. That is a decision,
not a fix, and it is written up in the task.

## Surprises

1. **The word-boundary regex lost its backslashes twice** on the way through a heredoc — the
   harness turns `\b` into a backspace. `chr(92)` is the workaround; noted in AGENTS-style
   memory for this environment.
2. **`Node.ledger` was a property**, so the head cache written in the same session never
   survived one access. Found by the profile refusing to improve.
3. **The live site's scorecards are byte-identical to the fixtures** (both from the
   2026-09-11 publish), so `--live` and the URL ingest correctly accept zero today. The test
   asserts that, because it is the dedupe working, not the port failing.

## Not done

- **Settlement for observations** (`kb-mpc`): a Trooth revision as a correction.
- **The tap** (KNP-6): the dashboard polls the store in-process.
- **Envelopes over the wire**: waiting on Trooth's `/fetch`.
- **Deploying the site page**: a human runs `npm run deploy` after merging the PR.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_trooth_node.py -q
uv run python examples/trooth-node/build.py
uv run streamlit run examples/trooth-node/dashboard.py -- examples/trooth-node/cell
```
