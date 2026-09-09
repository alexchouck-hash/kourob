# Glossary

From brief section 2. Terms here are load-bearing: use them exactly.

| Term | Meaning |
|---|---|
| **Node** | One folder, one process, one manifest. Owns a scope, an event store, a compiled knowledge base, a tool registry, a ledger, and a set of execution tiers |
| **Set** | A group of nodes under one operator, sharing a registry and a trust root. A set is what a builder publishes |
| **Scope** | What a node answers: a declared list of schemas, entities, and capabilities plus an embedding-free scope classifier (rules first, small model second) |
| **Port** | A standard interface: MCP (agent to tool), A2A (node to node), REST, events (SSE + webhooks), files, git |
| **Event** | An immutable, typed, provenance-stamped fact. The canonical form of everything the node knows |
| **Page** | A compiled markdown view over events, with a citation to an event id on every claim |
| **Receipt** | A signed record of one request: who asked, what was asked, which tier answered, which events and nodes contributed, cost in credits, hash of the response, hash of the previous receipt. The unit of provenance and metering |
| **Chain** | The path a request took through nodes, reconstructed from receipts |
| **Tier** | An execution path ordered by cost: T0 rules/SQL/cache, T1 distilled model, T2 mid model, T3 frontier model, T4 human. The node always tries the cheapest tier that meets its quality bar |
| **Referral** | A refusal that names another node likely to answer |
| **Bridge** | A referral the node executes on the caller's behalf, once, returning the answer plus the direct route so the caller does not need the bridge next time |
| **Trainer** | A frontier LLM session that builds or improves a node: writes schemas, labels gold data, distills tiers, proposes splits. Trainers are expensive and run offline; they do not serve requests |
| **Evolve** | The scheduled loop that reads the node's request log and receipts and changes the node to serve them better |
| **Split** | A node spawning a child node for a distinguishable cluster of demand, then referring that cluster to the child |
| **Credit** | The metering unit. Internal in v1; convertible to money or tokens later |

## Data zones

| Zone | Meaning |
|---|---|
| **bronze** | Raw source material as received. DVC-tracked, expires per retention policy |
| **silver** | Gated, validated, deduped, typed events. Written only by `gate.py` |
| **gold** | Human-verified labels and evaluation sets. Reachable from training code only through `evals/` |
| **quarantine** | Pushes that failed the gate, with the reason. Read by the `evolve` loop |
| **derived** | Anything rebuildable from silver. Deletable at any time |
