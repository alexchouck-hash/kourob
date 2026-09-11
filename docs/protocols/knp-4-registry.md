# KNP-4: Sets, registries, routes, trust

Status: draft · Milestone: M4 · Extension URI: `https://kourob.org/ext/registry/v1`
Depends on: KNP-0, KNP-1, KNP-2 · Decides: ADR-0003

There is no global registry, and there will not be one. Discovery is local, learned, and
signed.

## 1. Three ways a node learns about another node

| Mechanism | Latency | Trust | Cost |
|---|---|---|---|
| **Set registry** — the operator publishes a signed list | instant | set trust root | free |
| **Referral / bridge** — another node names it (KNP-1) | one request | as good as the evidence receipt | one request |
| **Manual** — `kourob routes add` | instant | operator's word | free |

Nothing else. In particular there is no crawl, no gossip, and no broadcast. A node's route
table grows from work it actually did, which bounds it to the size of its real traffic.

## 2. The set registry

A **set** is a group of nodes under one operator, sharing a registry and a trust root. It
is what a builder publishes.

```json
{
  "set": "did:key:z6MkSetRoot...",
  "name": "houck/tennis",
  "updated": "2026-09-09T21:00:00Z",
  "nodes": [
    {
      "node": "did:key:z6MkShot...",
      "name": "tennis-shot-node",
      "endpoint": "https://shots.example/a2a",
      "card": "https://shots.example/.well-known/agent-card.json",
      "scope_digest": "sha256:44ab...",
      "ledger_root": { "root": "sha256:9f21...", "size": 184203, "ts": "2026-09-09T21:00:00Z" }
    }
  ],
  "peers": ["did:key:z6MkOtherSet..."],
  "sig": "<ed25519 by the set root key>"
}
```

Served at `/.well-known/kourob-set.json`. Sets peer by exchanging registries; peering is
explicit and mutual, and it conveys *discovery*, not trust (§5).

## 3. The route table

Each node keeps `routes.parquet`:

| column | meaning |
|---|---|
| `scope_pattern` | what the route is for |
| `node`, `endpoint` | who |
| `observed_price`, `observed_latency_ms` | measured, not advertised |
| `last_success`, `last_failure` | decay inputs |
| `source` | `registry` / `referral` / `bridge` / `manual` |
| `evidence` | receipt id proving the last success |
| `score` | computed |

```
score = success_rate × recency_decay(last_success) / (observed_price × latency_penalty)
```

Advertised price is a claim; `observed_price` is what the receipt said. **When they
disagree, the route table records the observation and the score falls.** A node that
overquotes gets routed around without anyone adjudicating a dispute.

## 4. Ledger transparency

Per ADR-0003, v1 is a per-node signed hash chain. v1.1 adds a Merkle root over each node's
receipts, published into the set registry on a fixed interval.

- **Inclusion proof**: a caller holding `rcpt_X` can ask the node for a path proving `X` is
  under the published root. Establishes the node cannot later deny issuing it.
- **Consistency proof**: between two published roots, proves the earlier log is a prefix of
  the later. Establishes the operator did not rewrite history between publications.

This is the Certificate Transparency / Rekor pattern, and its guarantee is exactly theirs:
**tamper-evidence, not tamper-proofing.** The damage window for a compromised node is one
publication interval. Public anchoring beyond the set registry is deferred until three or
more independent operators exist and need to settle without trusting each other — see
ADR-0003, which also records why a blockchain buys nothing before that point.

## 5. Trust levels

Discovery and trust are separate. A node's manifest sets a policy:

| Policy | Will call | Will accept route hints from |
|---|---|---|
| `set-only` | nodes in its own set | its own set |
| `peered` | own set + peered sets | own set + peered sets |
| `evidenced` | any node whose card verifies **and** whose route hint carries an evidence receipt | any, weighted by evidence |
| `open` | any node whose card verifies | any |

Default is `peered`. `open` is for experiments and is refused by the `lint` loop on any node
with a non-empty `accounts.parquet`, because an open node with a balance is a node that will
eventually pay a stranger.

### 5.1 Route poisoning, honestly

A malicious node can return route hints that point at itself or at a colluder. v1's
defences are partial and worth naming:

- **Evidence receipts** raise the cost of lying: a fabricated hint carries no receipt signed
  by the node it names. Real, but a colluding pair can sign for each other.
- **Observation beats advertisement**: the route score is driven by measured price and
  latency, so a lie is corrected on first use — at the cost of one bad request.
- **Set scoping** bounds the blast radius to nodes the operator chose.

What is **not** solved in v1: cross-set reputation, collusion between peered sets, and
sybil resistance. Brief §15 defers this to an ADR after three operators exist, and that is
still the right call — reputation systems built before there is anything to have a
reputation about are always wrong.
