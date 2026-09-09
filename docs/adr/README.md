# Architecture Decision Records

One file per decision, numbered, using `TEMPLATE.md`. Every choice marked **ADR** in
`docs/brief/07-kourob-development.md` gets a record **before** it is implemented. No
option may be rejected without a spike in `docs/spikes/` or an explicit
"not explored because ..." line.

| ADR | Title | Status | Milestone |
|---|---|---|---|
| [0001](0001-store-interface.md) | Store interface, Parquet + DuckDB default | accepted | M0 |
| [0002](0002-license-apache-2.0.md) | License: Apache-2.0 | accepted | M0 |
| 0003 | Ledger design (hash chain, Merkle, blockchain question) | not written | M4 |
| 0004 | Price function | not written | M4 |
| 0005 | Auto-split criteria | not written | M4 |
