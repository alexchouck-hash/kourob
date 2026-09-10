# KNP-5: Outcomes, tier promotion, split and merge

Status: draft · Milestone: M4–M5 · Extension URI: `https://kourob.org/ext/outcome/v1`
Depends on: KNP-0, KNP-2 · Decides: ADR-0005, ADR-0007

How an individual node gets cheaper and better at its own job. This is the spec with the
least prior art and therefore the one most likely to be wrong; it is written so it can be
measured and falsified rather than believed.

## 1. The fitness function

A node has one number it is trying to reduce and three constraints it must not break.

```
minimise   cost_per_settled_request
subject to  quality_multiplier   ≥ q_floor        (KNP-3 §3)
            derived_share        non-decreasing   (KNP-0 §2)
            declared_scope       unchanged without a human   (KNP-1 §7)
```

**`cost_per_settled_request`, not `cost_per_request`.** A node can drive cost per request to
near zero by answering badly and fast. Dividing by *settled* requests — those with an
outcome inside their window — means an answer nobody could check, or one that came back
`corrected`, does not count as work done. This is the single most important choice in this
spec, and it is the reason KNP-2 §6 exists.

The three constraints exist because each blocks a way of cheating the objective: answering
worse, answering less verifiably, or quietly narrowing what "the job" means.

## 2. The unit of evolution: the demand cluster

The evolve loop does not optimise the node. It optimises **clusters of demand**, discovered
from the request log.

A cluster is a set of requests that share: the scope-classifier label, the schemas touched,
the tools called, and the shape of the answer. Clustering is over those discrete features —
not over embeddings. Requests are short and their features are already typed; an embedding
would add a dependency, a failure mode, and no accuracy.

Each cluster carries, per window:

| | |
|---|---|
| `volume` | requests in window |
| `tier_mix` | share served at each tier |
| `cost_per_settled` | the objective, restricted to this cluster |
| `settle_rate` | fraction with an outcome inside the window |
| `accept_rate` | of settled, fraction `accepted` |
| `event_fanout` | distinct events cited per request |
| `answer_entropy` | distinct answers per distinct (question, event-set) |

A cluster key is built from the **decision path** for an answered request — the rule or tier
that decided, the schemas touched, the tools called, the answer shape — and from the
**question frame** for a refused one, because a refusal has no decision path and refusals
are exactly where declared scope and real demand disagree.

The frame is the part of a question that survives changing its subject: "what is a bridge"
and "what is a cell" share one; "who wins wimbledon" does not. Keeping the *subject*
instead is the obvious mistake and it is worth naming, because it looks like clustering and
is not: every topic becomes its own cluster, which is the same as not clustering at all.

`answer_entropy` is the promotion signal. A cluster where the same events and question
always produce the same answer is a **function**, and functions belong in T0.

## 3. The promotion ladder

Work moves down the ladder as evidence accumulates. Each rung has an evidence gate, and no
rung may be skipped.

```
 T3 frontier ──▶ T2 mid ──▶ T1 student ──▶ T0 rule
   attested       attested     attested      derived
```

### 3.1 T3 → T2: few-shot capture

**Gate**: ≥ `n_fewshot` (default 50) settled-accepted answers in the cluster, `accept_rate`
≥ 0.9.
**Action**: select a few-shot set from the accepted answers, pin a prompt, route the cluster
to T2 with a confidence bar.
**Verify**: replay the held-out settled requests through T2. Promote only if T2's accept
rate on replay is within `tol_t2` (default 2 points) of T3's.

### 3.2 T2 → T1: distillation

**Gate**: ≥ `n_distill` (default 1000) settled examples, and a **gold set exists** for this
cluster. A node without gold cannot enable T1 — enforced in code, per brief §15.
**Action**: train the student on settled-accepted examples; calibrate the confidence bar on
gold, per class.
**Verify**: student within `tol_t1` (default 2 points) of the teacher on gold, **per class**,
not on average. A student that matches on aggregate while collapsing a rare class is the
classic distillation failure and an average hides it.

### 3.3 T1 → T0: rule mining by replay

This is the rung that produces the cost curve, and it works differently from the others.

**Gate**: `answer_entropy` = 1.0 over ≥ `n_rule` (default 200) settled requests — that is,
the answer has been a pure function of (question shape, cited events) every time observed.

**Action**: propose a candidate rule — a SQL view over silver, or a deterministic template.
The candidate is *mined* from the cluster, not written by hand: the shared structure of the
question, the join implied by the cited events, and the shared shape of the answer.

**Verify by replay** — the part that matters. Run the candidate over the **historical
request log**, not a sample, and compare to the settled answers:

```
promote iff  replay_exact_match == 1.0  over every settled request in the cluster
             and coverage ≥ min_coverage (default 0.95) of the cluster's volume
```

Not "within tolerance". **Exact, on every one.** A rule that is 99% right is a rule that is
wrong, because promoting it moves the answer from `attested` to `derived` and a `derived`
answer claims a third party can re-run it and get the same thing. Anything less than exact
launders a guess into a verifiable-looking receipt, which KNP-2 §5 calls the worst failure
the protocol can have.

Requests in the cluster the rule does not cover keep falling through to T1. Coverage is
allowed to be partial; correctness on what it covers is not.

### 3.4 Why this is where the money is

T0 costs a SQL scan. T3 costs a frontier call — three to four orders of magnitude more. The
5× cost target in `GOAL.md` does not come from a better model; it comes from noticing that
most of a mature node's traffic is a small number of functions being recomputed by a
language model. The frontier model's job was to *discover* the function. Once it is
discovered, running it through a frontier model is pure waste.

Promotion also **raises** the `derived_share`, so the node becomes more independently
checkable as it becomes cheaper. Cost and trust move the same direction here, which is
unusual and worth protecting.

## 4. Payback: when promotion is worth doing

Training is not free, and a cluster that is about to stop being asked about is not worth
distilling. Every promotion proposal carries a payback estimate:

```
saving_per_request = price_at_current_tier − price_at_target_tier
expected_remaining = volume_last_window × persistence(cluster)
payback_requests   = training_cost / saving_per_request

propose iff  payback_requests < expected_remaining × payback_margin   (default 0.5)
```

`persistence` is estimated from the cluster's own volume history — a cluster that has been
asked about steadily for eight weeks is a better bet than one that spiked yesterday. A
proposal that fails payback is recorded in the evolve report and **not** raised as a PR;
the point of writing it down is that next window it may pass, and the loop should not
re-derive it from scratch.

## 5. Demotion

Promotion without demotion is a ratchet, and ratchets break. A tier is demoted when the
evidence that justified it stops holding:

| Trigger | Action |
|---|---|
| A `derived` (T0) answer receives a `corrected` outcome | **Immediate.** Disable the rule, route the cluster back to T1, open a PR with the counter-example. A rule is exact or it is gone |
| T1 accept rate falls below `tol_t1` of T3 on a rolling gold re-eval | Raise T1's confidence bar so more falls through; retrain next cycle |
| The underlying schema changes | Invalidate every rule and student that reads it. No exceptions, no grace period |
| Cluster `settle_rate` collapses | Freeze promotion for that cluster. Unverifiable work does not get cheaper |

The first row is the important one. Exactly one counter-example kills a T0 rule, because
the rule's whole claim was that it is a function. One counter-example disproves that.

## 6. Scope shedding

Splitting is for nodes with too much demand. Shedding is for nodes with too much **surface**,
which is the more common problem and the one the brief does not name.

The `lint` and `evolve` loops track, per declared schema and tool:

- requests served in the last `shed_window` (default 90d)
- storage and tier weight carried for it

A declared schema with zero served requests over the window and a non-trivial carrying cost
produces a **shed proposal**: drop the schema from the declaration, delete its tiers and
derived data, move its silver to cold storage, and add an `excludes` entry pointing at
whoever should own it.

Three ways a schema earns its place, and only the first is obvious:

1. **requests cite it** — it is being read;
2. **events arrive under it** — it is being written, and a write nobody reads today may be
   what settles an answer tomorrow;
3. **another contract names it in `settles_against`** — it is load-bearing for settlement,
   and shedding it would quietly stop the node ever learning again.

The third was found by running the loop and watching it propose shedding the schema that
settles everything else. A shed rule that only counts reads will eventually delete a node's
ability to improve.

Shedding is what keeps a node small. A node's size should track its *demand*, not its
history, and without an explicit mechanism it will only ever grow. Like a split, a shed is a
PR with evidence and a human accepts it — it narrows a published contract.

## 7. Split and merge

Per brief §5.2 and ADR-0005. A split is proposed when **both** hold:

1. `demand_factor` has exceeded `split_threshold` for `split_window` (default 14d), **and**
2. ≥ 2 clusters each above `min_cluster_share` (default 0.2) touch mostly disjoint schemas
   or tools.

Both, because either alone produces thrash: high demand on one coherent cluster is a
scaling problem, not a splitting problem, and two clusters at low volume are not worth two
nodes.

The proposal PR contains the child manifest, the narrowed parent scope, the parent's new
referral rule, the cluster evidence, and the payback estimate. **A split inherits the
parent's promotion state for its clusters** — the child does not relearn what the parent
already distilled; the tiers and rules for its clusters are copied, and the parent deletes
them.

Merge is the inverse, on a longer window (`merge_window`, default 30d), when two siblings
are both under `merge_threshold`. The asymmetry between the windows is the hysteresis, and
it is deliberate: a wrong split costs two nodes' overhead until someone notices, and a
wrong merge costs a re-split.

## 8. What the evolve loop actually emits

One report per run, and at most one PR per proposal. Never a silent change.

```yaml
evolve_report:
  node: did:key:z6MkShot...
  window: 2026-08-27..2026-09-10
  objective:
    cost_per_settled_request: 0.0041      # was 0.0067
    derived_share: 0.34                   # was 0.19
    quality_multiplier: 0.94
  clusters: [...]
  proposals:
    - kind: promote            # T1 -> T0
      cluster: agg-serve-pct
      evidence: { replay_exact_match: 1.0, coverage: 0.97, n: 412 }
      payback_requests: 0
      pr: null                 # opened on approval
    - kind: shed
      schema: doubles_point.v1
      evidence: { requests_90d: 0, storage_mb: 341, tiers: 1 }
    - kind: split
      clusters: [shot-detail, serve-stats]
      evidence: { demand_factor: 1.42, days_over: 17, shares: [0.55, 0.45] }
    - kind: rule_from_quarantine
      evidence: { reason: "validate.enum: drop_shot", n: 88 }
  declined:
    - kind: promote
      cluster: rally-length-pred
      why: "payback_requests 9100 > expected_remaining 3400 x 0.5"
```

`declined` is not noise. It is the loop's memory: next window the same proposal is
re-evaluated against fresh volume rather than re-derived, and a proposal that is declined
five windows running is itself a signal that the cluster is not worth serving.

## 9. Cross-node distillation, and why it needs consent

A node that bridges the same narrow slice to the same upstream hundreds of times is, in
effect, being taught. It could distil the upstream's answers into its own T1 and stop
paying. This is technically easy and it is how the network dies: every node quietly
strip-mines its upstreams, upstream revenue collapses, and nobody maintains the source of
truth.

So it is governed rather than banned:

```yaml
# in the upstream's agent card, ext/meter/v1 params
derivation:
  policy: forbidden | attributed | licensed
  attribution_required: true
  royalty_credits_per_derived_answer: 0.0002
```

- `forbidden` — answers may be used, not learned from. A derived tier trained on this
  node's answers is a violation, detectable because the derived tier's receipts must
  declare their training provenance.
- `attributed` — allowed; every answer served from the derived tier carries the upstream's
  `did:key` in `citations` and the receipt's `model_version` records the derivation.
- `licensed` — allowed with a per-answer royalty debited to the upstream's account.

A receipt whose `model_version` names a student MUST record that student's `trained_from`
set. That is what makes the policy checkable rather than aspirational: derivation is
visible in the ledger, and a node violating an upstream's policy is provably doing so.

**This is unsolved in the general case** — nothing stops an operator training offline on
answers they legitimately paid for. The mechanism raises the cost of doing it invisibly
inside the protocol, which is worth something, and it is honest about not being a fence.

## 10. Falsifiable claims

This spec is wrong if any of these fail on `examples/tennis-node`:

1. `cost_per_settled_request` on day 30 ≤ ⅕ of day 1 (`evals/cost_curve.py`).
2. `derived_share` is non-decreasing across 30 days of replay.
3. A T0 rule promoted by replay never receives a `corrected` outcome in the replay window.
4. A synthetic bimodal log proposes a split; a noisy unimodal one does not
   (`evals/split_test.py`).
5. A cluster with `settle_rate` 0 never promotes past T2.

Numbers 3 and 5 have no test yet. They are the two most likely to be wrong.
