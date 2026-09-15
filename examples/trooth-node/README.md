# trooth-node

The first cell fed from outside this repository, and the first one a person can watch.

[Trooth](https://github.com/alexchouck-hash/trooth-site) is the single data connector and
provenance pipe: one MCP server or REST API resolves a request to verified upstream sources,
fetches, and wraps the answer in an ed25519-signed envelope that carries the source's identity,
licence, timestamps, freshness lag in seconds and a content hash. It also publishes a mechanical
scorecard per source on its [public site](https://alexchouck-hash.github.io/trooth-site/).

A KouroB node holds both as events. Trooth says *where a number came from and how late it is*;
the node says *which of those numbers it used to answer you*, signs a receipt for the answer,
and gets cheaper at the question the more it is asked. The two provenance chains meet at the
citation: an answer cites an event, the event carries Trooth's content hash and signature.

## Build it

Nothing generated is committed (keys are secret, Parquet is binary). Build the cell from the
fixtures in under a second:

```bash
uv run python examples/trooth-node/build.py
```

That runs `kourob init`, installs the two contracts and two T0 rules committed here, and pushes
the fixtures through the gate: one NWS envelope from Trooth's schema examples and the five
scorecards Trooth published (`fixtures/`). Add `--live` to also pull today's scorecards from the
public site. The same builder runs in `tests/test_trooth_node.py`, so the example and the test
cannot drift apart.

Then ask it:

```bash
uv run kourob query "latest observation at KJFK" --node examples/trooth-node/cell
```

```
KJFK at 2026-09-10T18:51:00Z: 21.1 C, humidity 65%, wind 14.5 km/h, Partly Cloudy. Source nws
(https://api.weather.gov/stations/KJFK/observations/latest), 412.0s behind the station,
content sha256:e3b0c442... [evt_...]

  tier        T0 (derived)
  citations   evt_...
  receipt     rcpt_...
```

```bash
uv run kourob query "how fresh is open-meteo" --node examples/trooth-node/cell
```

Both answer at T0: a rule, a SQL query over silver, no model, a citation to the event. Keep
feeding it:

```bash
# a file or a tree of envelopes / scorecards
uv run kourob ingest path/to/envelopes --from-trooth --node examples/trooth-node/cell
# or the public site: reads its manifest and every scorecard it lists
uv run kourob ingest https://alexchouck-hash.github.io/trooth-site --from-trooth --node examples/trooth-node/cell
```

The gate dedupes on `(source_id, snapshot_id)` for observations and `(source_id, generated_at)`
for scorecards, so re-ingesting is free and a *changed* snapshot with the same key is a
contradiction that lands in quarantine, not silently in silver.

## Watch it

The dashboard is Streamlit, the common open-source choice for a Python data app, and it is
deliberately generic: it reads the node through `open_node` and the Store API, never a Parquet
path, and asks questions through `serve.answer` like any other caller, so every question it puts
to the node leaves a receipt. Point it at a different cell and it shows that cell.

```bash
uv sync --extra ui
uv run streamlit run examples/trooth-node/dashboard.py -- examples/trooth-node/cell
```

Four panels: what the node holds (observations with their provenance, the scorecards), how it is
serving (tier share and cost per request by day, the two GOAL.md numbers), whether the receipt
chain verifies, and a box to ask it something. `tests/test_trooth_node.py` renders it headless
with Streamlit's own test harness, so a broken panel fails CI.

## What it demonstrates

- **A second provenance system, kept whole.** The in-port (`kourob.ports.trooth`) lifts the
  envelope's provenance beside its payload and keeps the payload's shape, which belongs to the
  upstream source. Trooth's signature rides along so the envelope can be re-verified later.
- **Quarantine is respected across systems.** Trooth quarantines upstream free text as a
  prompt-injection risk. The in-port does not re-admit it into silver, where a T3 tier would
  read it; the event records how many strings were dropped.
- **A human tap that is just a caller (KNP-6).** The dashboard has no node-specific code and no
  access to the node's files. When the SSE tap ships, it will subscribe instead of polling.
- **Honest about what is not built.** `kourob doctor` reports the `outcomes` check red: nothing
  settles an observation answer yet. The natural correction is a Trooth *revision* (same source
  timestamp, different content hash), and that comparator is `kb-mpc`. The `/fetch` endpoint
  that serves envelopes is not public yet, so envelopes come from files; `fetch_envelope` is in
  the port for when it is.

## Layout

```
examples/trooth-node/
  build.py          init + contracts + rules + fixtures, in one call
  dashboard.py      the Streamlit tap
  contracts/        observation.v1, scorecard.v1 (ODCS)
  rules/            observation-latest, scorecard-lookup (T0)
  fixtures/         one envelope, five scorecards, Trooth's manifest
  cell/             generated, gitignored
```
