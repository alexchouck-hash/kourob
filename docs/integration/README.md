# Integration

How existing work becomes KouroB nodes. Each file here is a concrete plan for one set, with
the mapping written out and the gaps named.

| Set | Source repos | Status |
|---|---|---|
| [tennis](tennis-set.md) | `tennis-live-stream-analysis`, `tennis-predict`, `tennis-predict-site` | planned, M3–M5 |

The general lesson from the first one: **do not port a working system into a node.** Wrap
it. A node is a manifest, a gate, a ledger, and some ports; the thing that already works
stays where it is and becomes a tier or an ingest source. Rewrites lose the accuracy that
justified the node in the first place.
