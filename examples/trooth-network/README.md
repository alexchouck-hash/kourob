# trooth-network

Seven cells. One node per Trooth feed, a weather desk over two of them, a front desk over
all. A question to the front crosses up to three nodes, every hop receipted, price and cost
summed along the chain. And the network says what it uses: every feed with its licence and
attribution, every Trooth scorecard page, every source's Modafied emblem.

```
                         ┌─────────────┐
   ask ────────────────▶ │ trooth-desk │  the front: holds nothing, refers by declared exclusions
                         └──┬───┬───┬──┘
              ┌─────────────┘   │   └──────────────┬───────────────┐
              ▼                 ▼                  ▼               ▼
       ┌──────────────┐    usgs-node          bls-node        fred-node
       │ weather-desk │    usgs-earthquake    bls cpi         (card + emblem only)
       └───┬──────┬───┘
           ▼      ▼
      nws-node  open-meteo-node
```

Each source node holds three kinds of event: the feed's **observation** (a Trooth-shaped
envelope), Trooth's **scorecard** for the feed, and the feed's **Modafied emblem**.

## The emblems

[Modafied](https://modafied.org/) is an independent benchmark, funded by Trooth, measured by
the same code for every source. These are the feeds this network holds, as Modafied rates
them today. Each emblem is Modafied's own SVG, linked to its scorecard page, embedded the way
its emblems page prescribes:

[![Modafied benchmark grade C for National Weather Service API, 2.4 of 4 points across 5 of 6 dimensions, ranked 2 of 2 in weather](https://alexchouck-hash.github.io/modafied-site/v1/emblems/nws.svg)](https://alexchouck-hash.github.io/modafied-site/scorecards/nws)

[![Modafied benchmark grade A for Open-Meteo Weather API, 4.0 of 4 points across 4 of 6 dimensions, ranked 1 of 2 in weather](https://alexchouck-hash.github.io/modafied-site/v1/emblems/open-meteo.svg)](https://alexchouck-hash.github.io/modafied-site/scorecards/open-meteo)

[![Modafied benchmark grade B for USGS Earthquake Hazards Program, 3.17 of 4 points across 6 of 6 dimensions, ranked 1 of 1 in geophysical hazards](https://alexchouck-hash.github.io/modafied-site/v1/emblems/usgs-earthquake.svg)](https://alexchouck-hash.github.io/modafied-site/scorecards/usgs-earthquake)

[![Modafied benchmark: Bureau of Labor Statistics Public Data API has insufficient data for a rating (2 of 6 dimensions measurable)](https://alexchouck-hash.github.io/modafied-site/v1/emblems/bls.svg)](https://alexchouck-hash.github.io/modafied-site/scorecards/bls)

[![Modafied benchmark: Federal Reserve Economic Data (FRED) has insufficient data for a rating (0 of 6 dimensions measurable)](https://alexchouck-hash.github.io/modafied-site/v1/emblems/fred.svg)](https://alexchouck-hash.github.io/modafied-site/scorecards/fred)

> Mechanically computed from public snapshots. This is a measurement, not an endorsement, a
> verification, or a partnership. It cannot be purchased and it changes without notice when
> the measurement changes.

The emblems above are live images; the grades change when Modafied's measurement changes.
Inside the network they are held as `emblem.v1` events. The Modafied in-port
(`kourob.ports.modafied`) **verifies each attestation before it is pushed**, the way the
emblems page says a consumer should: the attestation's scorecard hash must match the one
Modafied's manifest lists, and a consumer that cannot verify fails closed. An attestation
with the wrong hash, or one the manifest does not list, is refused and never becomes an event.
The event keeps the notice verbatim, and the T0 rule that answers "modafied grade of nws" puts
the notice on the answer, because an emblem shown without it is not the emblem Modafied issued.

## Build it

```bash
uv run python examples/trooth-network/build.py
```

Under two seconds. Uses the envelopes from `../trooth-set/fixtures` (Trooth-shaped snapshots
of the real sources, signed locally; see that README), the scorecards from `../trooth-node`,
and the Modafied attestations, emblems and manifest in `fixtures/modafied/` (copied from
Modafied's published `v1/`, same trace ids as the live site at the time of copying). The
Trooth catalog entries in `fixtures/trooth-catalog/` supply each feed's attribution text.
`tests/test_trooth_network.py` builds it the same way.

## Ask the front

```bash
uv run kourob query "nws observation at KJFK" --node examples/trooth-network/cells/trooth-desk
uv run kourob query "modafied grade of usgs-earthquake" --node examples/trooth-network/cells/trooth-desk
uv run kourob query "what is the latest cpi" --node examples/trooth-network/cells/trooth-desk
```

The first crosses three nodes: the front refers weather to the weather desk, which refers
`nws` to nws-node, which answers from a rule and cites the envelope. Both desks bridge once
for a caller and refer after that; `kourob trace <receipt>` on the front follows the routes
transitively and returns all three receipts.

## The credits

`build.py` writes `cells/credits.md`, and any node can write its own:

```bash
uv run kourob publish --credits --node examples/trooth-network/cells/nws-node
```

It is generated from what the nodes hold, never hand-written: the feeds via Trooth (source
URL, licence, the attribution text the catalog asks for, which nodes hold it, the Trooth
scorecard page), the Trooth scorecards used as UI outputs (page links with the freshness and
completeness the card reports), and the Modafied emblems, embedded with the notice.

## Watch it

```bash
uv sync --extra ui
uv run streamlit run examples/trooth-network/dashboard.py -- examples/trooth-network/cells
```

The network as a graph (each source node labelled with its Modafied grade), the Ask box to
the front with the receipt chain across nodes, and a "what this network uses" panel: per node,
the feed with its hash and licence, the Trooth scorecard link, and the Modafied emblem image
with its trace id. The generated credits page is at the bottom. Rendered headless in CI.

## Layout

```
examples/trooth-network/
  build.py                    seven cells, connected, credits.md written
  dashboard.py                the network dashboard (Streamlit)
  contracts/emblem.odcs.yaml  emblem.v1
  rules/emblem-lookup.yaml    "modafied grade of <source>"
  fixtures/modafied/          Modafied attestations, emblems (SVG), manifest.json
  fixtures/trooth-catalog/    Trooth's catalog entries, for attribution text
  cells/                      generated, gitignored
```
