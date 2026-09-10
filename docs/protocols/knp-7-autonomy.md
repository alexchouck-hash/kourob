# KNP-7: Autonomy, budget, and self-sustaining nodes

Status: draft · Milestone: M4–M6 · Depends on: KNP-2, KNP-3, KNP-5

KNP-5 says what a node should change about itself. This says **what it may change without
asking**, what it pays for that with, and when it must stop and fetch a human.

A node that needs a human for every improvement is a project. A node that needs one for
none is a hazard. The whole design here is the ladder between those.

## 1. The one thing autonomy never includes

**A node may become better at its job. It may not change what its job is.**

Widening declared scope — adding a schema, an entity, a capability — always requires a
human, at every autonomy level, forever. Everything else on this page is negotiable.

The reason is containment (KNP-0 I3), and it is not a safety platitude: other nodes have
routed to this one *because of its declaration*. A node that widens its own scope
invalidates every route table pointing at it and every referral rule that names it. It is
the one change whose blast radius leaves the node.

Narrowing is different. A node may shed scope it does not serve (KNP-5 §6) at A3, because
narrowing only ever produces referrals, and a referral is a correct answer.

## 2. The autonomy ladder

Levels are **earned by evidence and revoked by breach**, exactly like tier promotion. A new
node starts at A0.

| | Level | May do, without asking | Blast radius if wrong |
|---|---|---|---|
| **A0** | observe | Nothing. Every change is a proposal | none |
| **A1** | tune | Adjust confidence bars, cache size and TTL, route scores, retry and timeout budgets — within bounds declared in the manifest | one node, one window, reversible from the event log |
| **A2** | promote | Everything in A1, plus: retrain T1, mine and enable T0 rules, promote and demote tiers, adjust few-shot sets | one node's answers, bounded by KNP-5 evidence gates; demotion is already automatic |
| **A3** | restructure | Everything in A2, plus: shed unserved scope, split itself, merge with a sibling, propose schema versions | this node and its children; **referrals leave the node**, so a split is announced to the set registry |
| **A4** | fund | Everything in A3, plus: spend its own credits on trainer sessions and upstream calls without per-session approval, within a standing budget | this node's balance |

Two things are deliberately absent from every level: widening scope (§1), and changing the
node's own autonomy level. **A node cannot promote itself.** Graduation is computed by the
set operator's tooling from the node's ledger, not asserted by the node.

### 2.1 Graduation

A node graduates from level *n* to *n+1* when, over `graduation_window` (default 4 evolve
cycles), **all** hold:

- every change it auto-applied at level *n* survived — no demotion, no rollback, no
  `corrected` outcome traceable to an auto-applied change;
- `quality_multiplier` did not fall;
- `derived_share` did not fall;
- `settle_rate` stayed above `settle_floor` — a node whose answers stop being checkable
  loses the evidence that justifies trusting it with more;
- `kourob ledger verify` passed on every cycle.

### 2.2 Demotion

Immediate, automatic, one level, on any of: a rolled-back auto-applied change; a
`quality_multiplier` below `q_floor`; a failed `ledger verify`; a scope-drift detection
(KNP-1 §7); or a `policy` refusal (KNP-1 §6).

Demotion is not a punishment and it is not appealable in-band. It is the same mechanism as
a T0 rule being disabled by one counter-example: the evidence that justified the privilege
stopped holding, so the privilege stops.

## 3. The budget: what makes a node self-sustaining

Autonomy without a budget is just a node making free changes, which means nothing selects
against bad ones. So every autonomous action is paid for out of the node's own balance.

```
surplus = revenue − serving_cost − evolution_cost
```

- **revenue** — `Σ price_credits` on receipts where this node was the answerer.
- **serving_cost** — `Σ cost_credits`: tokens, compute, upstream prices (KNP-3 §1).
- **evolution_cost** — trainer sessions, distillation compute, replay passes, the loops
  themselves. Metered exactly like serving, through the same runner, into the same log.

Metering evolution through the same runner as serving is the point. It means the cost of
improving a node is visible in the same units as the cost of running it, and a promotion's
payback calculation (KNP-5 §4) is denominated in something real.

### 3.1 Three states

| State | Condition | Behaviour |
|---|---|---|
| **growing** | `surplus > evolution_budget` | Funds its own trainer sessions. Evolution runs at full cadence. Eligible to graduate |
| **stable** | `0 < surplus ≤ evolution_budget` | Serves fine; evolution throttled to what the surplus covers. Cheap loops (lint, prune, rule mining) continue; expensive ones (trainer, distillation) queue |
| **failing** | `surplus ≤ 0` | Cannot pay for itself. Three moves, in order: raise price (KNP-3 §1 already does this under demand), shed unserved scope (KNP-5 §6), then **halt and report** |

**A failing node is information, not an incident.** A node nobody calls earns nothing,
cannot fund its own improvement, and stops improving — which is the correct outcome. The
alternative is a set full of nodes being subsidised into permanent mediocrity by an
operator who has forgotten they exist.

This is the selection pressure the whole design needs and does not otherwise have. Demand
funds specialisation (KNP-5 §7 split); absence of demand funds nothing.

### 3.2 Free-tier and bootstrap

A new node has no revenue and cannot be self-sustaining on day one. The manifest declares a
`bootstrap_grant` in credits from the set operator, and a `bootstrap_window`. A node still
in `failing` when its grant runs out halts and reports rather than drawing further. **The
operator must decide again, deliberately, to keep funding it.** Silent perpetual subsidy is
how a set accumulates nodes nobody wants.

## 4. `kourob tend`: the self-development cycle

One command, one budget, one report. This is the thing a cron job runs and a node's whole
autonomous life consists of.

```bash
kourob tend --node . --budget 5.0 --autonomy-max A2
```

```
   ingest ──▶ compile ──▶ lint ──▶ evolve ──▶ decide ──▶ apply | propose ──▶ reflect
      │          │          │         │          │            │              │
   quarantine  pages     flags   proposals   autonomy      events +       report
                                             + budget       PRs
```

**decide** is the only new step. For each proposal from `evolve`, it answers three
questions in order, and any "no" turns an apply into a propose:

1. Is this within the node's current autonomy level (§2)?
2. Does the budget cover it, and does it pay back (KNP-5 §4)?
3. Is it reversible — is there a recorded inverse that `kourob rollback` can apply?

Question 3 is the one that does real work. **A change with no recorded inverse is never
auto-applied, at any level.** Enabling a T0 rule is reversible (disable it). Retraining T1
is reversible (the previous student is kept for `rollback_window`). Shedding scope is
reversible only if the data was cold-stored rather than deleted — which is why KNP-5 §6
says cold-store, not delete.

### 4.1 Every auto-applied change is an event

```yaml
id: evt_01JC...
schema_ref: node_change.v1
payload:
  kind: promote | demote | tune | shed | split | merge | retrain
  autonomy_level: A2
  proposal: { ... }               # the evolve proposal, verbatim
  evidence: { replay_exact_match: 1.0, coverage: 0.97, n: 412 }
  cost_credits: 0.84
  inverse: { kind: demote, rule: agg-serve-pct }   # what rollback would do
  applied_at: 2026-09-10T04:12:00Z
provenance:
  activity: "loop:tend"
  agent: "did:key:z6MkShot..."
```

So a node's self-modification history is in the same event store, under the same schema
discipline, cited by the same receipts as everything else. `kourob trace` on an answer that
came from an auto-promoted rule reaches the change event that promoted it, and from there to
the evidence. **A node can explain not just what it answered but why it is the shape it is.**

### 4.2 Halt conditions

`tend` stops, applies nothing further, and reports, on any of:

| Condition | Why it is a halt and not a warning |
|---|---|
| `ledger verify` fails | Every piece of evidence `tend` would reason from is now untrusted |
| `quality_multiplier < q_floor` | The node is getting worse; more autonomous change makes it worse faster |
| `settle_rate` below floor | Nothing can be verified, so nothing should be promoted |
| scope drift detected | The node is answering outside its declaration — a containment breach |
| budget exhausted mid-cycle | Half-applied evolution is worse than none |
| a `policy` refusal occurred (PII, consent, minors) | Never auto-resolved. DEFAULTS.md escalation criteria |
| two consecutive rollbacks | Something is wrong with the evidence gates themselves |

A halt demotes the node one autonomy level (§2.2) and opens one PR with the report. It does
not stop the node *serving* — serving and tending are separate, and a node that cannot
safely improve itself can usually still answer.

## 5. Repair: adapting without being told

The loops already produce the signals; `tend` is what acts on them.

| Signal | Source | Repair | Level |
|---|---|---|---|
| Same quarantine reason ≥ `n_quarantine` times | gate | Propose a schema version or a gate rule. The `drop_shot` enum gap in `evals/gate_fixtures/` is exactly this | A3 (propose at A0+) |
| A route's `observed_price` diverges from advertised | routes | Decay the score. No dispute, no adjudication | A1 |
| A route fails `n_fail` times | routes | Drop to `unavailable`, re-refer, keep the evidence | A1 |
| A T0 rule gets one `corrected` outcome | outcomes | Disable immediately, open a PR with the counter-example | A2 |
| Upstream schema changed | registry | Invalidate every rule and student reading it. No grace period | A2 |
| A cluster's `settle_rate` collapses | outcomes | Freeze promotion for that cluster; flag the settlement source | A1 |
| Declared schema with zero traffic in `shed_window` | evolve | Propose a shed | A3 |

The pattern is the same each time: **a node adapts by noticing that evidence it relied on
stopped holding, and withdrawing what that evidence justified.** It is a much duller
mechanism than "learning", and it is the one that can be trusted to run unattended.

## 6. A set of nodes tending itself

Nothing above is coordinated. Each node runs its own `tend` against its own ledger and its
own budget. What makes a *set* coherent is that they share a registry and a trust root, and
that three things propagate:

1. **Schema versions.** A node that publishes a new schema version announces it in the set
   registry; consumers invalidate derived tiers (§5) and re-promote against the new shape.
2. **Split announcements.** A split changes routing, so the child is added to the registry
   and the parent's referral rule is published with it.
3. **Autonomy levels.** Published per node in the registry, so a caller can see how
   autonomously its upstream is being changed. A node at A4 is a different counterparty
   from one at A0, and that should be visible before you route to it.

There is deliberately no set-level optimiser, no scheduler, and no shared queue. A set is a
trust boundary and a name space, not a control plane. Nodes coordinate through routes,
receipts and the registry, or not at all.

## 7. Falsifiable claims

1. A node at A2 running unattended for 30 simulated days never widens its declared scope.
2. Every auto-applied change has a recorded inverse, and `kourob rollback` restores the
   prior objective within one cycle.
3. A node with zero traffic reaches `failing`, halts, and does not consume budget after its
   bootstrap grant expires.
4. A node whose quality falls below `q_floor` demotes its own autonomy level before it
   applies another change.
5. Two consecutive rollbacks halt the node.

None of these has a test yet. Claim 2 is the one the whole design leans on and the one most
likely to be quietly false, because "reversible" is easy to assert and hard to prove for
retraining.
