# 2026-09-13 · claude-code · trooth-set: four cells connected, and the provider outputs

Task: `kb-58t`. The ask: connect multiple KouroBs as an example, with a couple of UI outputs
modelled on what Trooth gives a provider (trooth-site/providers).

## Done

### The set — `examples/trooth-set/`

Three data nodes (weather: nws + open-meteo at KJFK; seismic: usgs-earthquake; economy:
bls, with the fred card) and a desk that holds nothing but three declared exclusions and
three routes. `build.py` makes all four and connects them in under a second;
`tests/test_trooth_set.py` (10 tests) builds it the same way and proves:

- the desk **bridges** an earthquake question to seismic-node (T0 there), cites the event,
  hands back the route with an evidence receipt; `trace` on the desk returns **two receipts
  across two nodes** and the desk's receipt names its upstream;
- the **second** call is a referral, not a bridge (`bridge_limit: 1`);
- a direct question to weather-node names its source, and nws and open-meteo are two
  events with two citations.

The envelopes are Trooth-shaped snapshots of the real public sources, built by
`fixtures/make_envelopes.py` and **signed locally with `key_id: kourob-local`** because
Trooth's `/fetch` is not public (decision 97). They validate against Trooth's envelope
schema, vendored with the catalog and scorecard schemas under `fixtures/trooth-schemas/`.

### The provider outputs — `src/kourob/publish.py`, `kourob publish --trooth`

The two documents Trooth's provider page describes, generated from a node's own records
and validated against Trooth's schemas in the test (decisions 94, 95):

- `catalog.yaml`: the node as a feed - held schemas as fields, held sources as lineage,
  their licence, metered cost with the node's capacity window;
- `scorecard.json`: the six dimensions - freshness lag (answer time minus newest cited
  event), revision behaviour and correction latency (from settled outcomes), completeness
  by tier, schema stability (`node_change.v1` count), internal consistency (quarantined
  contradictions) - and `accuracy` when anything has settled.

### The set dashboard — `examples/trooth-set/dashboard.py`

Streamlit. The route graph (Graphviz, rendered client-side) with each route's source,
strength and successes; an Ask box to the desk with the answer, the route handed back, and
the **receipt chain across nodes with price and cost summed along it**; one tab per node
with the scorecard numbers, the catalog entry and the meter report side by side. Verified in
the browser and rendered headless in CI.

### A correctness bug in the perf work, found by the set

The per-handle store caches from `kb-0sl` showed each handle a different node: a bridge
wrote through the local transport's handle and the test's handle never saw the request
(scorecard: 0 requests). Caches are now shared per resolved node directory within a process
(decision 96); `Store.refresh()` exists for the one caller that edits files behind the
store's back (`tamper_for_test`).

## Not done

- **Deploying the site page**: trooth-site#1 now also describes the set; still not deployed.
- **Listing a node in Trooth's catalog for real**: the entry is generated; submitting it is
  a PR to Trooth's private repo, which is the operator's call.
- **Settlement for observations** (`kb-mpc`), so revision behaviour on the provider
  scorecard stops reading 0 by construction.
- **A2A card / HTTP** (`kb-imt`): the set talks on disk; the desk is what "one MCP server
  for the set" becomes when it has a wire.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_trooth_set.py -q
uv run python examples/trooth-set/build.py
uv run streamlit run examples/trooth-set/dashboard.py -- examples/trooth-set/cells
```
