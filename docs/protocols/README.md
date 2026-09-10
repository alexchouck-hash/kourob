# KouroB Node Protocol (KNP)

The wire contracts that make nodes composable. The brief describes the architecture; these
describe what actually crosses the boundary between two nodes, in enough detail that
someone can implement a KouroB node without reading our source.

| Spec | Subject | A2A extension URI | Milestone |
|---|---|---|---|
| [KNP-0](knp-0-core.md) | Invariants, versioning, the answer envelope | — | M1 |
| [KNP-1](knp-1-scope.md) | Scope, refusal, referral, bridge | `https://kourob.org/ext/scope/v1` | M3 |
| [KNP-2](knp-2-receipt.md) | Receipts and provenance | `https://kourob.org/ext/receipt/v1` | M1 |
| [KNP-3](knp-3-meter.md) | Price quotes and credit settlement | `https://kourob.org/ext/meter/v1` | M4 |
| [KNP-4](knp-4-registry.md) | Sets, registries, routes, trust | `https://kourob.org/ext/registry/v1` | M4 |
| [KNP-5](knp-5-evolution.md) | Outcomes, tier promotion, split and merge | `https://kourob.org/ext/outcome/v1` | M4–M5 |

## Reading order

KNP-0 first: it defines the three invariants everything else assumes. Then KNP-2, because
provenance is the load-bearing one — a KouroB node without receipts is just an HTTP
service. KNP-1 is what makes a node *contained*. KNP-3 and KNP-4 make a network of them
economical. KNP-5 is what makes an individual node get cheaper, and it is the one with the
least prior art, so it is the one most likely to be wrong.

## Relationship to A2A and MCP

KouroB does not define a transport. It defines four A2A extensions (per
[ADR-0006](../adr/0006-a2a-extensions-over-namespaced-fields.md)) and one MCP tool
convention. A KouroB node **is** an A2A agent and **is** an MCP server; the extensions add
scope, provenance, and metering to calls that would otherwise work fine without them.

A caller that activates no extensions still gets an answer. It just gets an answer it
cannot trace, cannot price, and cannot follow a referral from. That is the honest trade,
and it is deliberate: adoption should not require the whole stack.

## Status

Draft. These specs are versioned in their URI. A breaking change mints a `/v2` URI and both
may be served during a transition; an additive change does not. Nothing here is stable
until the milestone in the table above has passed.
