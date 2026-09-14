# 2026-09-13 · claude-code · trooth-network: seven cells, Modafied emblems, credits

Task: `kb-6b5`. The ask: a KouroB node network on Trooth feeds, advertising Modafied with
its emblems, using Trooth's UI outputs, and advertising every feed and UI output used.

## Done

### The network — `examples/trooth-network/`

One node per Trooth feed (nws, open-meteo, usgs-earthquake, bls, fred), a weather desk over
the two weather nodes, a front desk over everything. A weather question from the front
crosses three nodes; `trace` now follows routes transitively (decision 101) and returns
three receipts. `tests/test_trooth_network.py`: 11 tests.

### The Modafied in-port — `src/kourob/ports/modafied.py`

Modafied (modafied.org) is the independent benchmark funded by Trooth; per source it
publishes an attestation (grade, six dimensions, rank, evidence, emblem SVGs, a notice).
The port verifies the attestation's scorecard hash against Modafied's manifest and **fails
closed** - the check Modafied's emblems page tells consumers to make - then pushes one
`emblem.v1` event carrying the notice verbatim (decision 99). A tampered or unlisted
attestation is refused before the gate sees it; the test proves both refusals.

### The advertising

- **Emblems.** The network README embeds all five Modafied emblems in the exact markdown
  form Modafied's emblems page prescribes (full emblem, linked to the scorecard page), with
  the notice under them. The dashboard shows each source's emblem image, trace id and
  scorecard link beside the feed's Trooth scorecard; the graph labels each node with its
  grade. A T0 rule answers "modafied grade of usgs-earthquake" with the notice attached.
- **Credits.** `kourob publish --credits` (new module `src/kourob/credits.py`) writes a
  page from what a node holds: every feed with licence and the attribution text Trooth's
  catalog entry asks for, every Trooth scorecard page, every Modafied emblem. `build.py`
  writes one for the whole network (decision 100).

### Fixtures

Modafied attestations, emblems and manifest copied from Modafied's published `v1/` (trace
ids match the live site at copy time); Trooth catalog entries for attribution text;
envelopes reused from `trooth-set`. FRED has no envelope (needs an API key), so fred-node
holds a card and an emblem only, and says so in its scope.

## Not done

- **Live refresh of emblems**: `fetch_attestations` exists; nothing schedules it. A weekly
  `tend` action that re-pulls attestations and re-verifies them is the natural next step.
- **Modafied benchmarking KouroB itself**: Modafied benchmarks MCP servers; a node's MCP
  port could be measured by it. That is Modafied's PR to make, not this repo's claim.
- **Deploying the site page** (trooth-site#1): still the operator's call.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_trooth_network.py -q
uv run python examples/trooth-network/build.py
uv run streamlit run examples/trooth-network/dashboard.py -- examples/trooth-network/cells
```
