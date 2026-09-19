# Architecture Decision Records

One file per decision, numbered, using `TEMPLATE.md`. Every choice marked **ADR** in
`docs/brief/07-kourob-development.md` gets a record **before** it is implemented. No
option may be rejected without a spike in `docs/spikes/` or an explicit
"not explored because ..." line.

| ADR | Title | Status | Milestone |
|---|---|---|---|
| [0001](0001-store-interface.md) | Store interface, Parquet + DuckDB default | accepted | M0 |
| [0002](0002-license-apache-2.0.md) | License: Apache-2.0 | accepted | M0 |
| 0003 | Ledger design (hash chain, Merkle, blockchain question) | not written — drafted as [KNP-4](../protocols/knp-4-registry.md) | M4 |
| 0004 | Price function | not written — drafted as [KNP-3](../protocols/knp-3-meter.md) | M4 |
| 0005 | Auto-split criteria | not written — drafted as [KNP-5](../protocols/knp-5-evolution.md) §7 | M4 |
| [0006](0006-a2a-extensions-over-namespaced-fields.md) | A2A extensions, not a `kourob.*` namespace | accepted | M3 |
| [0007](0007-outcomes-and-the-settled-request-objective.md) | Outcomes as a ledger record; cost per *settled* request | accepted | M4 |
| [0008](0008-t0-promotion-by-exact-replay.md) | T0 promotion requires exact replay | accepted | M5 |

A protocol draft in `docs/protocols/` is not an ADR. The drafts state what the wire looks
like; the ADRs above record why, with the rejected options. 0003 to 0005 are still owed
before their milestone implements anything.
