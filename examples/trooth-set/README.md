# trooth-set

Four cells, connected. Three hold data from Trooth's catalog sources; one holds nothing and
knows who does. Ask the desk anything in the three domains: it bridges once, hands back the
direct route with an evidence receipt, and refers after that. Every hop is receipted, and the
price and cost along the whole chain are on screen.

Then the part [Trooth's provider page](https://alexchouck-hash.github.io/trooth-site/providers/)
describes: a data owner lists a feed as one catalog entry and gets a public six-dimension
scorecard. A KouroB node is such a feed, so `kourob publish --trooth` writes both documents
for each node, in Trooth's own schemas, from the node's own records.

```
                ┌──────────────┐
   ask ───────▶ │  trooth-desk │  holds nothing; three declared exclusions, three routes
                └──┬────┬────┬─┘
        bridge/refer│    │    │
        ┌───────────┘    │    └────────────┐
        ▼                ▼                 ▼
  weather-node      seismic-node      economy-node
  nws, open-meteo   usgs-earthquake   bls (+ fred card)
  observation.v1    observation.v1    observation.v1
  scorecard.v1      scorecard.v1      scorecard.v1
```

## Build it

```bash
uv run python examples/trooth-set/build.py
```

Under a second. Each data node is `kourob init` plus the contracts from `../trooth-node` and
its own T0 rules (`rules/<node>/`), fed from `fixtures/envelopes/` and the scorecards Trooth
published. The desk is `kourob init` plus three exclusions (`earthquake|quake|...` refers to
seismic-node, and so on) and `kourob connect` to each. `tests/test_trooth_set.py` builds it
the same way, so the example cannot drift from the test.

**About the envelopes.** Trooth's `/fetch` endpoint is not public yet, so
`fixtures/make_envelopes.py` does what Trooth's snapshot job does - fetch each catalog
endpoint, hash the bytes, stamp the fetch time - and wraps it in Trooth's envelope schema,
**signed by a local key with `key_id: kourob-local`**. That key id is the honest marker: these
prove what was fetched and when, by this operator, not by Trooth. They validate against
Trooth's envelope schema (vendored in `fixtures/trooth-schemas/`), and nothing downstream
changes the day real ones arrive.

## Ask the desk

```bash
uv run kourob query "largest earthquake in the last hour" --node examples/trooth-set/cells/trooth-desk
```

```
Largest of 7 quakes in the hour to 2026-09-14T00:17:10Z: M2.41 5 km S of Indios, Puerto Rico
at 2026-09-13T23:29:01Z, depth 11.05 km. Source usgs-earthquake (https://earthquake.usgs.gov/...)
[evt_…]

  tier        T0 (derived)          ← seismic-node answered from a rule
  citations   evt_…                 ← its event, with Trooth's content hash on it
  receipt     rcpt_…                ← the desk's receipt, naming the upstream receipt
```

Ask again and the desk **refers** instead: the caller has had its one introduction
(`bridge_limit: 1`) and now holds the direct route. `kourob trace <receipt>` on the desk walks
both receipts and the event behind them.

```bash
uv run kourob query "what is the latest cpi" --node examples/trooth-set/cells/trooth-desk
uv run kourob query "open-meteo observation at KJFK" --node examples/trooth-set/cells/weather-node
```

## The provider outputs

```bash
uv run kourob publish --trooth --node examples/trooth-set/cells/seismic-node
```

```
seismic-node: 1 requests; freshness p50 240.7s p95 240.7s; complete 100.0%; consistent 100.0%; revisions 0.0%
  catalog    examples/trooth-set/cells/seismic-node/out/trooth/catalog.yaml
  scorecard  examples/trooth-set/cells/seismic-node/out/trooth/scorecard.json
```

- **`catalog.yaml`** (Trooth `schema/catalog/v0.1`): the node as a feed. Its held schemas
  become `fields`, the sources it holds become `declared_lineage.upstream_sources`, the
  licence is the one its sources carry, and `cost` is `metered` with the node's own
  capacity window. Submit it as a PR to Trooth's catalog and the node is listed.
- **`scorecard.json`** (Trooth `schema/scorecard/v0.1`): the six dimensions, from what the
  node records. Freshness lag is answer time minus the newest cited event's time. Revision
  behaviour and correction latency come from settled outcomes. Completeness is in-scope
  requests answered, by tier. Schema stability counts `node_change.v1` events. Internal
  consistency counts the contradictions the gate quarantined. A node with no traffic gets a
  scorecard that says so.

Both validate against Trooth's schemas in the test.

## Watch it

```bash
uv sync --extra ui
uv run streamlit run examples/trooth-set/dashboard.py -- examples/trooth-set/cells
```

Three panels. **The set**: the nodes and their routes as a graph, with each route's source
and Hebbian strength. **Ask the desk**: a question through `serve.answer`, the answer, the
route handed back, and the chain of receipts across nodes with price and cost summed along
it. **What Trooth would show**: one tab per node with the scorecard's numbers, the catalog
entry, and the node's meter report side by side.

The dashboard reads every cell through `open_node` and the Store API and has no node-specific
code; it is rendered headless in CI.

## What it demonstrates

- **Referral and bridge across a real set** (KNP-1 sections 4 and 5), with chained receipts
  and `trace` crossing nodes. The second call goes direct.
- **Metered along the whole chain** (GOAL.md): price and cost per hop, summed, on screen.
- **A node is a Trooth provider.** The two documents a provider needs, generated from the
  node's own records, in Trooth's schemas.
- **Honest fixtures.** Locally signed envelopes say so in their key id.

## Layout

```
examples/trooth-set/
  build.py                  four cells, connected, in one call
  dashboard.py              the set dashboard (Streamlit)
  rules/{weather,seismic,economy}/   T0 rules per node
  fixtures/envelopes/       Trooth-shaped snapshots of nws, open-meteo, usgs-earthquake, bls
  fixtures/make_envelopes.py         refresh them from the live sources
  fixtures/trooth-schemas/  Trooth's envelope, catalog and scorecard schemas (v0.1), vendored
  cells/                    generated, gitignored
```
