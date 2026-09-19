# KNP-9: Synapses — connection, Hebbian routing, and pruning

Status: draft · Milestone: M3–M5 · Depends on: KNP-1, KNP-4, KNP-5

Cells describe containment. This describes the opposite half: how connecting is made cheap,
how connections strengthen with use and fade without it, and how everything unused is
collected.

The useful analogy here is not a service mesh. It is a neuron: connections are
overproduced, reinforced by successful firing, and aggressively pruned. Most of what a brain
does while developing is **removing** connections, and that is the part software
architectures reliably forget.

## 1. Connecting must be one command

If connecting two cells is harder than importing a module, people will import the module and
the membrane is gone (KNP-8 §2.2). So the ergonomics are a requirement, not a nicety.

```bash
kourob connect https://shots.example        # a node
kourob connect did:key:z6MkShot...          # a node, by identity
kourob connect ./sibling-cell               # a node on disk
kourob connect --set https://houck.example  # every node in a set
```

One command does all of it: fetch `/.well-known/agent-card.json`, verify the card signature
against the `did:key`, read the declared scope, price and autonomy level, check the trust
policy (KNP-4 §5), write a route row, and emit a `connection.v1` event. No config file, no
service registry, no code generation, no restart.

Disconnecting is symmetric and equally cheap:

```bash
kourob disconnect did:key:z6MkShot...   # drops the route; keeps the receipts
```

**A connection is data, not code.** That is what makes it revocable, meterable, and
prunable. Nothing about connecting produces an import, a generated stub, or a build
dependency.

## 2. Signal: what "firing" means

A cell receives a request, checks it against its scope, and either fires (answers) or does
not (refuses or refers). The confidence bar in the cascade is the activation threshold: a
tier fires when its confidence clears the bar, and otherwise the signal propagates to a more
expensive tier, and then out of the cell as a referral.

Two properties follow, and both are already specified elsewhere; they are worth naming
together:

- **A refusal is a signal, not a failure** (KNP-1). It carries a route. A cell that refuses
  well makes the network faster.
- **Signal strength is confidence, and it is carried**, not discarded. A bridged answer
  keeps the upstream's citations; an ungrounded span is marked rather than laundered
  (KNP-2 §5).

## 3. Hebbian routing

A route's score rises with successful use and decays without it.

```
on success:   strength ← strength + α × (1 − strength)
on failure:   strength ← strength × (1 − β)
each window:  strength ← strength × decay_per_window
```

Defaults: `α = 0.3`, `β = 0.5`, `decay_per_window = 0.9`. Failure is punished harder than
success is rewarded, and everything fades.

The effective routing score combines strength with what the receipts actually observed:

```
score = strength × recency(last_success) / (observed_price × latency_penalty)
```

`observed_price` and `observed_latency` come from receipts, never from the neighbour's
advertisement (KNP-4 §3). A neighbour that overquotes loses score without anyone
adjudicating a dispute.

**Decay is what makes this work.** A route that was good a year ago and has not been used
since is not evidence about today. Without decay, a route table is an archive; with it, it
is a picture of what currently works, and its size is bounded by real traffic rather than by
history.

## 4. Pruning and garbage collection

The `prune` loop runs weekly and is a first-class output of `tend` (KNP-7 §4), not cleanup
that happens eventually. Six things are collected, each with a different rule:

| What | Collected when | Recoverable? |
|---|---|---|
| **Routes** | `strength` below `prune_floor` (default 0.05) for `prune_window` | Yes — re-learned from one referral |
| **T0 rules** | `usage_count` zero for `rule_window`, or disabled by a counter-example | Yes — re-mined from the log |
| **Tiers** | No cluster routes to them after a promotion or shed | Yes — retrainable from the call log |
| **Derived data** | Always collectable; rebuilt on demand | Yes, by definition |
| **Bronze** | Past retention, and its silver events exist | No — this is why it is DVC-tracked |
| **Pages** | Not pulled for `page_window` | Yes — regenerated from events |

Two things are **never** collected: **events** in silver, and **receipts and outcomes**. They
are the ground truth and the provenance record. Everything else in a cell is a cache of
those two, and saying so precisely is what makes aggressive collection safe.

That is the answer to a 750 MB `artifacts/` directory. Almost none of it is ground truth;
nearly all of it is derived, and it survives only because nothing was ever charged with
noticing that nothing reads it.

### 4.1 Usage counters are the whole mechanism

Every prunable thing carries a usage counter incremented on read: a T0 rule hit, a page
pull, a route success, a tier invocation. Counters decay per window like route strength, so
"used once a year ago" converges to zero.

This is cheap — one counter increment on a path that is already writing a receipt — and it
is the only thing that makes deletion decidable. **A system that cannot say what is unused
cannot delete anything, and therefore grows forever.**

### 4.2 Prune is proposed at A0–A2 and automatic at A3

Under KNP-7 the autonomy ladder governs this too. At A0 the prune loop reports. At A3 it
collects derived data, cold pages, and dead routes on its own, because every one of those is
recoverable and the change carries its inverse. Bronze past retention is always a proposal:
it is the only prunable class that is not recoverable.

## 5. Growth is connection, not accumulation

Putting KNP-8 and this spec together gives the shape the whole design is aiming at:

- A cell **cannot grow** past its ceiling. It sheds or divides (KNP-8 §3).
- A network **grows by connecting**, and connecting is one command and one row (§1).
- Connections **strengthen with use and fade without it** (§3).
- Everything derived is **collected when unused** (§4).

So the system's capacity grows while any individual piece of it stays small enough for one
agent to hold in context. That is the property being bought, and it is the only one that
matters for building this way over years rather than weeks.

## 6. Falsifiable claims

1. `kourob connect <url>` produces a working route with no file edited by hand and no
   restart.
2. A route unused for `prune_window` falls below `prune_floor` and is collected.
3. A collected route is re-learned from a single referral, with no loss of function.
4. Replaying 30 days of traffic leaves total cell size flat or falling while answered volume
   rises.
5. No prune run ever deletes an event, a receipt, or an outcome.

Claim 4 is the one that says whether any of this works. Claim 5 is the one that must never
fail.
