# 06: KouroB, Trooth, Modafied

**One system, three layers. Optimized for performance, filtered by three tests, written to direct Claude Code.**
Status: plan v0.2, 2026-09-14. Supersedes v0.1. Extends `05-trooth-data-quality-layer.md`, `CLAUDE.md` (Trooth), and `02-model-distillation-for-task-execution.md`.

v0.2 adds: the anatomy of a node (section 3), the routing design and the answer to "should Trooth control it" (section 4), Modafied as an open, replicated grader (section 5), how Trooth gets data and why anyone would contribute (section 6), the contract set (section 7), three-repo layout (section 8), and a queue seed for Claude Code (section 11).

---

## 0. The one-sentence version, and what to read first

Trooth fetches external data inside a provenance envelope. KouroB answers repeated questions by replaying short, graded chains of distilled models instead of calling a frontier model. Modafied grades sources, nodes, and paths with open, reproducible code against named anchors. The thing that compounds is the graded trace corpus and the snapshot archive, neither of which can be backfilled by anyone who starts later.

The frontier model is not the competitor. It is the miss handler, the planner, the teacher, and the adjudicator. It never sits in a hot path.

**Claude Code: read in this order before writing anything.** `CLAUDE.md` (Trooth constitution; its hard rules H1 to H12 apply to all three repos unless a rule below overrides one explicitly), this file, `02-model-distillation-for-task-execution.md` sections 2 and 5, `05-trooth-data-quality-layer.md` sections 3 and 6, then the relevant repo's ADRs. Do not build anything from a phase whose gate (section 10) is unmet.

---

## 1. What "performance" means, and the ranked levers

Performance is cost and latency per correct answer at a fixed accuracy floor, measured end to end.

| # | Lever | Mechanism | Why it ranks here |
|---|---|---|---|
| 1 | **Path memoization** | Plan the chain once per query class, cache by class signature, replay | Cost per query falls with traffic. This is the business |
| 2 | **Exact memo** | Hash the typed input; identical input returns the cached typed output | Deterministic models make this free, and repeated inputs are common in every target domain |
| 3 | **Path collapse** | Fold a hot, stable path into one node trained on the path's own outputs | Removes hops and serialization loss; accuracy usually rises |
| 4 | **Distill to code** | When a collapsed node is near-deterministic on a small input space, replace it with a lookup or rule set | The last hop of efficiency; a table beats a model |
| 5 | **Typed payloads** | Every inter-node message validates against a schema; free text only in a quarantined field | Stops the network degenerating into a slow, worse language model; closes the injection surface |
| 6 | **Hop budget** | Four hops in the hot path, two after collapse | A 5M-parameter node runs in ~3ms; a network hop costs 20 to 50ms |
| 7 | **Planner distillation** | After a few thousand graded traces, distill the planning policy | Makes misses cheap; blocked until volume exists |
| 8 | **Cache-first fetch** | Trooth serves from versioned snapshot unless `freshness=live` | Most queries never touch an upstream |

Explicitly not optimized: volunteer training (about 1,000x behind frontier), peer-voted quality (captured or gamed everywhere it has been deployed), tokens or chains (attract gaming before customers), GPUs in a hot path (a node that needs one is not distilled enough), and open-ended consumer chat (no repetition, so no cache).

---

## 2. Three layers, one routing principle

```
caller (agent, app, 10xAnd tool)
   │  typed request
   ▼
KouroB  ─ exact memo? ─ path memo? ─ else queue for planner (budgeted)
   │  replay path: 2-4 hops, every hop typed and traced
   │  nodes that need external data call Trooth as if it were a node
   ▼
Trooth  ─ resolve source(s) by catalog + Modafied scorecards ─ fetch ─ envelope
   │
   ▼
Modafied ─ grades sources (six dimensions), nodes and paths (accuracy vs anchor,
           calibration, cost, latency, drift). Open code. Independent replicas.
```

**One routing principle, two routers.** Both KouroB and Trooth route the same way: resolve against a registry, rank candidates by Modafied scores under the caller's constraints, and emit `considered_and_rejected`. They differ in what they route. Trooth routes *fetches* (which source). KouroB routes *computation* (which nodes, in what order). Neither controls the other. Details in section 4.

**Layer rules.**
- Trooth never runs a model. Its routing is a lookup.
- KouroB never fetches an upstream directly. External data arrives as a Trooth envelope, so provenance is inherited, not reconstructed.
- Modafied never accepts a self-reported number. It grades from snapshots, traces, and anchors it can re-read, and anyone can rerun it.

---

## 3. Inside a KouroB node

A node is one process with one job. It is small, typed, stateless per request, and it learns only offline.

### 3.1 Anatomy

```
request (typed) ──▶ [1] validator ──▶ [2] exact memo ──▶ [3] feature adapter
                                                              │
                     [7] trace ◀── [6] escalation ◀── [5] calibrator ◀── [4] task model
                          │
                          ▼
                  [8] drift sampler (offline queue)     [9] gold slice (eval only, read-only)
```

| # | Component | What it does | Rule |
|---|---|---|---|
| 1 | Validator | JSON Schema check on input. Reject with a typed error, or **refer** (3.4) if the input is valid but out of scope | Never coerces. Never guesses |
| 2 | Exact memo | `sha256(canonical input)` → cached typed output, keyed by node version | Cleared on every version bump |
| 3 | Feature adapter | Deterministic code turning the typed input into model features | No model here; unit tested |
| 4 | Task model | The distilled student. 1M to 100M parameters, int8, ONNX Runtime, CPU. Multi-task heads allowed | No prompt, no free-text generation |
| 5 | Calibrator | Temperature scaling and per-class thresholds fitted on gold | Recalibrated after every retrain |
| 6 | Escalation | Below threshold: emit the student answer marked `provisional`, queue for teacher, or refer | Threshold is per class and published on the node's scorecard |
| 7 | Trace emitter | Input hash, output hash, confidence, duration, model version, envelope refs | A response without a trace is a bug |
| 8 | Drift sampler | 1 to 5% of served traffic held for offline teacher grading | Teacher never in the request path |
| 9 | Gold slice | The node's slice of the class gold set | Read by `make eval` only; CI fails if the trainer references it |

Everything outside the task model is shared library code. A new node is a contract, a feature adapter, weights, and a gold slice.

### 3.2 Node types

| Type | Output | Example | Anchor |
|---|---|---|---|
| Classifier | label + calibrated probability | shot stroke, report source, intent | gold labels |
| Extractor | typed fields | dates, amounts, k-numbers from structured records | gold fields |
| Linker | cluster or match id | MAUDE dedup, brand normalization | gold pairs |
| Scorer | ordered candidates with scores | which source, which node | downstream outcome |
| Normalizer | deterministic transform | unit conversion, schema mapping | exact test |
| Aggregator | rollup over a window | serve-speed trend, quarterly counts | recomputation |
| Fetch | a Trooth envelope | any external data | Trooth scorecard |
| Planner | a path DAG | class → chain of nodes | Modafied path grading |

Normalizers and Fetch nodes have no model. They exist so that paths are uniform: every hop is a node, every hop is traced.

### 3.3 Lifecycle

```
SEEDED     contract + gold slice exist; the "model" is a teacher call. Served only in shadow.
SHADOW     student runs on live traffic; teacher still answers; agreement measured.
SERVING    student answers; teacher grades the drift sample; Modafied scorecard is live.
COLLAPSED  this node absorbed a whole path (section 3.5). Old path retained as fallback and grader.
CODIFIED   replaced by rules or a table extracted from the model. Model retained for eval only.
RETIRED    superseded. Never deleted; traces still resolve.
```

Promotion rules are mechanical: SHADOW → SERVING when student-vs-gold meets the class floor and student-vs-teacher agreement is at or above 0.95 on two consecutive weekly samples. Demotion is automatic when the drift sample shows a two-week decline.

### 3.4 Referral and bridging

A node that receives valid but out-of-scope input does not error. It returns:

```json
{ "refer": true, "reason": "input.camera_setup=facility not in training distribution",
  "candidates": ["tennis.shot.facility"], "registry_query": {"task_type": "shot_label", "domain": "facility"} }
```

The planner records the referral, patches the path, and the patched path is graded like any other. This is the mechanism behind "the requesting node finds the shorter path": referrals are traced, so the planner learns which first hop was wrong for which input shape, and the next plan skips it.

### 3.5 Evolution: what "each pull leaves the node more useful" means mechanically

- **Every served request** produces a trace. **Low-confidence requests** get teacher labels. **Retraining** runs on a cadence with the new labels, bumps the version, refits the calibrator, and requests a Modafied regrade.
- **Split.** When per-class confusion shows a stable bimodal sub-distribution (broadcast vs facility camera; manufacturer vs facility reports), the archivist proposes splitting into two nodes with a cheap discriminator in front. A split ships only if both children beat the parent on their own slice and the discriminator is above 0.98.
- **Merge.** Two nodes whose input distributions overlap above 80% and whose scorecards are within a point get merged. Fewer nodes is the goal, not more.
- **Collapse.** A path is HOT when it has served over 1,000 queries in 14 days with no member version bump. Train one node on (path input → path final output), teacher is the path. Shadow it. Cut over when it is within 1 point on gold and at least 3x cheaper. The uncollapsed path stays as fallback and as the collapsed node's grader.
- **Codify.** When a node's input space is small and its output is near-deterministic (above 0.995 on gold), extract rules or a table. Ship the table. Keep the model for eval.

Thresholds above are hypotheses. Each lives in `config/thresholds.yaml`, versioned, and changing one needs an experiment entry.

### 3.6 Runtime and hosting

Nodes run as Python services (FastAPI + ONNX Runtime) on the existing VPS in v0, because that is where the team's strength is and because Cloudflare Workers cannot host ONNX. The TypeScript API layer (auth, metering, memo lookup, envelope assembly) stays on Workers. This is a deliberate exception to the Trooth "no second runtime in the hot path" rule and is recorded as KouroB ADR-0002. Migrate individual hot nodes to `onnxruntime-node` only if latency or VPS cost demands it.

---

## 4. Routing

### 4.1 Should Trooth control routing? No, and here is the split

Two different problems hide under "routing":

| Question | Owner | Nature | Model needed? |
|---|---|---|---|
| Which source should answer this fetch? | Trooth `resolve` | Lookup: catalog filtered by license, geography, fields, freshness; ranked by scorecard | No, in v0 |
| Which nodes, in what order, answer this query class? | KouroB `plan` | Decomposition: a planning problem over contracts | Yes, on a cache miss |

Putting the second inside Trooth would turn a data layer into a monolith and would couple the planner's failure modes to the pipe's uptime. Instead, **Trooth is a node.** The planner routes to it exactly as it routes to a classifier. Trooth's own `resolve` runs inside that hop. The two routers share a registry schema and share Modafied scores as their weights, which is all the coupling they need.

### 4.2 The four routing levels (each is a cache in front of the next)

| Level | Trigger | Mechanism | Cost |
|---|---|---|---|
| 0. Exact memo | Identical typed input seen before | Hash lookup | ~0 |
| 1. Class memo | `class_signature = hash(task_type, input_schema_id, constraint_fingerprint)` seen before | Cached path replayed | node inference only |
| 2. Planner | Unknown class, or a referral patched a path | Frontier model with the node registry, contracts, hop budget, cost ceiling, and the class gold set. Runs async under a hard monthly budget. Returns a path DAG and a written rejection list | one frontier call per new class |
| 3. Distilled planner | Enough graded plans exist (target: 2,000) | Small classifier proposes the path; frontier verifies a sample | near 0 |

Natural-language entry is deliberately absent from the hot path in v0. Callers submit typed requests with a declared `task_type`. A distilled intent classifier in front of level 1 is a Phase 2 item, and it is itself a node.

### 4.3 Ranking candidates for a hop (published, lexicographic, no weights to tune)

Among nodes registered for a `task_type`:
1. Drop any node without a Modafied scorecard newer than 30 days.
2. Drop any node below the class accuracy floor on its named anchor.
3. Drop any node whose p95 latency breaks the caller's budget.
4. Of the rest, pick the lowest declared cost.
5. Tie: most recently regraded.

Lexicographic beats a weighted product because every rejection has a one-line reason, and that reason goes in `considered_and_rejected`. Trooth's `resolve` uses the same five steps with the six-dimension scorecard in place of accuracy where no anchor exists.

### 4.4 Learning the route without relitigating it every request

Phase 2: keep up to three graded candidate paths per class. Serve by Thompson sampling on Modafied accuracy, with a floor on exploration (5%). Paths that lose for 30 days are retired. This is the only "learned routing" in the plan, it is cheap, and it is auditable because every arm's score is public.

### 4.5 Budget behavior on a miss

Free tier: no cached path means a `202 queued` with an estimated planning time, not an answer. Pro tier: metered pass-through to the planner up to the customer's own cap. The platform cap (50 USD/month, alert at 25) is never silently exceeded. Honest refusal is a feature.

---

## 5. Modafied

### 5.1 Role

The independent grader and the registry of anchors. It publishes:
- **Source scorecards**: the six dimensions (freshness lag, revision behavior, correction latency, completeness by segment, schema stability, internal consistency), plus accuracy only with a named anchor.
- **Node scorecards**: accuracy vs anchor, calibration error, cost per call, p95 latency, drift since last grade, gold-set version.
- **Path scorecards**: end-to-end accuracy, hop count, compounding loss (path accuracy vs product of hop accuracies), cost, p95.
- **The anchor registry**: for each domain, what counts as settleable truth, with its own provenance.
- **The method**, versioned, with a changelog and the reproduction command.
- **Replica attestations** (5.3).

It is separate from Trooth and KouroB because you cannot honestly grade pipes you resell or nodes you operate.

### 5.2 Open source: yes, all of it

The scoring code, the method, the anchor registry, and the scorecard schema are Apache-2.0 in their own repo. This is not generosity; it is the only way the claim "scores are mechanical and reproducible" can be checked. `make score --snapshot <id>` on public snapshots must produce a byte-identical scorecard on anyone's machine.

### 5.3 Crowdsourcing: what the crowd can and cannot do

| Crowd can | Crowd cannot |
|---|---|
| Run a **replica**: snapshot the same sources, compute scorecards, publish a signed hash. Agreement across independent replicas is the trust signal | Vote on a score |
| Propose **anchors** for a domain, with provenance, via PR | Set a score by hand |
| Contribute **catalog entries** and **quirk reports** (reviewed, then merged) | Bypass review |
| Contribute **gold labels** through a labeling tool with inter-annotator agreement measured and published | Contribute gold without agreement stats |
| Propose **metric definitions** and method changes via ADR + PR, versioned | Change the method for a source without changing it for all |
| File a **dispute** with a reproduction | File a dispute without one |

Replication is the real decentralization here. It needs no consensus, no tokens, and no honest-majority assumption: two replicas either produce the same hash from the same public snapshot or they do not, and a disagreement is a bug report. Target for Phase 2: three replicas on three different hosts, one not operated by Alex.

### 5.4 Governance and funding

- Method changes: ADR, PR, review by at least one maintainer who is not the author, new `method_version`, old version's scorecards kept.
- **No revenue from graded parties.** Modafied does not take listing fees, sponsorship, or advertising from any source, node, or provider it grades.
- Allowed revenue: grading a customer's *private, unpublished* sources or nodes on request (a service, not a score for sale); sponsorship from parties that are not graded; grants. Whether Modafied is a nonprofit, a foundation-style project, or simply a separate company with a published conflict policy is an open decision for Alex.
- Compute for public scorecards is funded by Trooth under a fixed, published, non-negotiable transfer that does not vary with any score. Publish the number.

### 5.5 Anti-gaming

Providers will optimize to the metric. The six dimensions are chosen so that gaming one degrades another: publishing early to win freshness raises revision rate; suppressing corrections to win revision rate raises internal inconsistency; padding fields to win completeness raises schema instability. Publish this trap on the method page. For nodes, the gold set is held out and rotated quarterly, and a node that has seen a gold item is regraded on the next rotation.

---

## 6. How Trooth gets data, and why anyone contributes

### 6.1 Supply tiers

| Tier | How it arrives | Incentive needed | Phase |
|---|---|---|---|
| Public and free sources | Trooth's own snapshot jobs (NWS, USGS, BLS, FRED, Census, openFDA, ECB) | None | 0 |
| Pass-through licensed | Customer brings credentials; Trooth routes, envelopes, caches privately | The envelope, history, and reconciliation over data they already pay for | 1 |
| Derived datasets | Trooth's own snapshot history and revision diffs | Trooth's product; licensable at 12+ months of history | 2 |
| Caller observations | Every fetch through the pipe is a freshness and consistency measurement | Passive; the free tier is the incentive | 1 |
| Provider-listed feeds, filters, layers, UIs | Providers list a catalog entry with a price | The ladder below | 3 |
| Contributed nodes | Contributors register a node that passes grading | Revenue share plus a free training loop | 4 |

### 6.2 The incentive ladder (what actually pulls, in order)

1. **Distribution.** Being in the catalog means every agent that uses Trooth can discover you. For a small provider this is worth more than the payout. "Routable" is the product they are buying.
2. **The scorecard as a credential.** A good Modafied score is public proof, like a security audit. Good providers want it; that is the same dynamic that made audits standard. Providers who refuse are listed as "unmeasured", which is itself a signal.
3. **Money.** Metered payouts, monthly, at a published take rate (default 20%, ADR at Phase 3). Providers set their own price; Trooth never prices their data.
4. **Free tooling.** Every listed provider gets revision monitoring, schema-change alerts, and freshness reports on their own feed. Most providers do not know their own revision behavior.
5. **Access credits.** Contributions earn quota on the pipe:

| Contribution | Credit |
|---|---|
| Catalog entry that passes review and gets a scorecard | quota bump |
| Snapshot mirror (a Modafied replica) | quota bump plus attestation listing |
| Gold labels with published agreement stats | quota bump proportional to accepted labels |
| Bug or quirk report that changes a scorecard | quota bump |
| A node that reaches SERVING | revenue share plus quota |

Credits only work if the free tier is genuinely limited but genuinely usable. Rule: the free tier never requires an account (Trooth H9); credits attach to a key on the paid tiers.

### 6.3 Why a node contributor would bother

Beyond revenue share: **the network trains your model for you.** A contributed node gets the drift sampler, teacher labels on its low-confidence traffic, retraining on cadence, calibration, and a public scorecard, none of which a solo builder can afford. "List your node and it gets better every week" is the pitch, and it is true only because the teacher, the gold sets, and the grader already exist.

Contribution is by invitation until Phase 4 and only in verifiable task classes (a gold set or a settleable anchor must exist). This is not caution for its own sake: a node in an unverifiable class cannot be graded, so it cannot be routed to, so listing it is pointless.

### 6.4 The cold start, solved in order

Buyers first (the free catalog and the public benchmark bring them), then providers (they come for distribution and the credential), then the marketplace (a second revenue line on top of a pipe that already works). This order is fixed. Reversing it is how marketplaces die.

---

## 7. Contracts (write these before any code)

Shared package `@modafied/schemas` (npm) mirrored to `modafied-schemas` (pypi), versioned, consumed by all three repos.

```
envelope/v0.1.json    Trooth response wrapper (CLAUDE.md 4.3, unchanged)
catalog/v0.1.json     source entry (CLAUDE.md 4.5, unchanged)
node/v0.1.json        id, task_type, domain, input_schema, output_schema, model_version,
                      cost_units, latency_p95_ms, escalation_threshold, eval_manifest_ref,
                      state (seeded|shadow|serving|collapsed|codified|retired), owner, license
path/v0.1.json        path_id, class_signature, hops[{node_id, version, contract_ref}],
                      measured{accuracy, anchor_ref, cost_units, p95_ms, compounding_loss},
                      state (planned|graded|memoized|hot|collapsed|retired), collapsed_into,
                      considered_and_rejected[]
trace/v0.1.json       request_id, path_id, hops[{node_id, version, input_hash, output_hash,
                      confidence, ms, envelope_refs[], refer?}], outcome_ref, blame_vector? (offline)
scorecard/v0.1.json   subject{type: source|node|path, id}, method_version, dimensions{...},
                      accuracy?{value, anchor_ref} (invalid without anchor_ref),
                      gold_set_version?, replica_attestations[]
anchor/v0.1.json      domain, description, provenance, settle_rule, url, last_verified
referral/v0.1.json    reason, candidates[], registry_query
```

Rules carried over from Trooth and extended:
- **H4 extended.** Every KouroB response carries its trace and the planner's `considered_and_rejected`.
- **H5 extended.** Free text from any upstream or any node is quarantined in `untrusted_text` and never enters a prompt, a catalog entry, or a downstream node without human review.
- **H7.** Contract first; schema before code; old major served 90 days.
- **K1 (new).** No node serves without a gold slice and a Modafied scorecard newer than 30 days.
- **K2 (new).** The trainer may not read `data/gold/`. CI greps training configs and fails on a reference.
- **K3 (new).** Thresholds live in versioned config; changing one requires an experiment entry.
- **M1 (new).** A scorecard is publishable only if `make score` reproduces it byte for byte from the referenced snapshot.
- **M2 (new).** Modafied takes no revenue from any party it grades.

---

## 8. Repos

Three repos, not one. Modafied's independence has to be visible in the org chart of the code.

```
trooth/          as specified in CLAUDE.md. Adds: nothing new in Phase 0.
kourob/
  CLAUDE.md      constitution; points at this doc and at Trooth's rules
  docs/          adr/ experiments/ spikes/ ideas/ handoffs/ runbooks/ (doc 01 system)
  registry/      one YAML per node (mirrors catalog/sources/ in Trooth)
  nodes/<id>/    contract.json, adapter.py, weights/, gold/ (eval-only), eval_manifest.yaml
  lib/           validator, memo, calibrator, escalation, trace, drift sampler (shared)
  planner/       frontier planner prompt pack, budget guard, path store; distilled planner later
  paths/         memoized paths as JSON, one file each, append-only
  api/           TypeScript Worker: auth, metering, memo lookup, envelope assembly
  runtime/       Python FastAPI + ONNX Runtime node host for the VPS
  trainer/       distillation jobs: shadow, retrain, collapse, codify (Python, offline)
  evals/         make eval: node-vs-gold, node-vs-teacher, path compounding, calibration
  config/        thresholds.yaml (versioned)
modafied/
  CLAUDE.md      constitution; M1, M2, replication rules
  method/        METHOD.md versioned, changelog
  scoring/       Python: six dimensions, node metrics, path metrics; make score --snapshot <id>
  anchors/       one YAML per anchor
  replicas/      how to run one; attestation format; list of known replicas
  gold/          registry of gold sets (pointers and versions, not the data)
  disputes/      one file per dispute, with reproduction
  site/          scorecards, method, anchors, replicas, disputes
```

Trooth's snapshot and scoring jobs from Phase 0 move to `modafied/scoring/` at the start of Phase 1. Trooth keeps the pipe; Modafied keeps the grader. Until that move, Trooth's `jobs/score` is the grader and the method page says so.

---

## 9. The three-axis evaluation (must clear all three)

| Component | Feasible | Viable | Desirable | Verdict |
|---|---|---|---|---|
| Trooth benchmark and pipe | Yes | Pipe yes, benchmark alone no | Yes: one connector, provenance, revision alerts | **Build.** |
| Modafied open grader | Yes, same code run separately | Indirect: credibility, private grading service | Strongly, for RA/QA and quant buyers; and for providers who are good | **Build.** |
| Modafied replicas | Yes: reproducibility, not consensus | Cheap | Yes for anyone who has to trust a score | **Build in Phase 2.** |
| KouroB exact and class memo | Yes | The margin | Users want the cost cut, not the mechanism | **Build. The core.** |
| Node anatomy and lifecycle | Yes; all standard pieces | Yes | Invisible, correctly | **Build with the first node.** |
| Referral and path patching | Yes | Yes | Invisible | **Build with the second node.** |
| Collapse and codify | Yes | Compounds the margin | Invisible | **Build once a path is HOT.** |
| Thompson-sampled paths | Yes | Modest | Invisible | **Phase 2.** |
| Contributor incentive ladder | Yes | Unproven until providers exist | Distribution and credential are real pulls; credits are speculative | **Build the ladder in Phase 3, credits last.** |
| Permissionless nodes | Only in verifiable classes | Unproven | Low today | **Phase 4, invited first.** |
| Tokens, chains, emissions | Yes | Negative | Undesirable to enterprise buyers | **Reject.** |
| Decentralized training | No, at any budget you have | No | No | **Reject.** |
| Consumer chat surface | Yes | No moat | The trap | **Reject.** |

The desirability test is a sentence with a yes or no answer: *will an agent developer replace one API call with one call to us, given a measured cost cut and a signed envelope?* Ask it of the first ten Phase 1 callers.

The viability test is a number: *the repetition rate of the first instrumented workload.* Under 20%, the cache thesis is wrong (section 12).

---

## 10. Sequencing with gates on all three axes

| Phase | Weeks | Ships | Technical gate | Commercial gate | Desirability gate |
|---|---|---|---|---|---|
| **0 Benchmark** | 1-3 | Trooth catalog of 5, snapshot/diff/score jobs, method page, static site | Scorecards byte-reproducible | under 5 USD/mo | Fresh-agent test passes; one outside reader asks to add a source |
| **0b First node** | 2-5 (parallel) | `maude.dedup` through SEEDED → SHADOW → SERVING, gold pairs, eval manifest, first node scorecard | Precision ≥ 0.85, recall ≥ 0.70 on gold; shadow agreement ≥ 0.95 | Slots into 10xAnd at no new cost | An RA/QA reader uses the scorecard unprompted |
| **1 Pipe and memo** | 4-10 | Trooth REST + MCP (six tools), signed envelopes; KouroB exact memo, class memo, budgeted planner, trace corpus; Modafied repo created and scoring moved into it | Cache hit ≥ 60% on the instrumented workload; p95 ≤ 400ms | 25 weekly active callers, one a 10xAnd tool | One external developer replaces a direct call and says why |
| **2 Collapse, replicas, paid** | 11-18 | First collapse; `trooth.route` as a node with referral; Stripe Pro tier; `as_of` replay; transparency log; three Modafied replicas; Thompson paths | Collapsed node within 1 pt on gold and ≥ 3x cheaper; replicas agree | First paying customer | That customer renews or expands |
| **3 Providers** | after gate | Provider listing, metering, payouts, take-rate ADR, free provider tooling, `tennis.shot` node | A provider's feed gets a scorecard without hand-holding | 3 providers, 1 paid feed transacting | A provider cites their scorecard publicly |
| **4 Contributors** | after gate | Invited node contribution in verifiable classes, revenue share, credits | A contributed node reaches SERVING unassisted | 3 contributors, 1 paid node transacting | A contributor returns with a second node |

Marketplace listing, permissionless participation, and anything token-shaped sit after Phase 4 and need a separate decision.

---

## 11. Queue seed for Claude Code

Populate `queue/backlog.md` in each repo from this list. Every item: acceptance criteria (tests, not opinions), context pointers, effort S/M/L, phase. Nothing from a later phase is built early; it goes in the backlog with its phase.

**trooth/** (Phase 0 items are already in `KICKOFF-PROMPT.md`; do not duplicate)
- T-11 (M, P1): `trooth.resolve` implements the five-step lexicographic ranking from 4.3 with the six-dimension card. AC: every rejection has a one-line reason; unit tests cover each step.
- T-12 (S, P1): Trooth is callable as a KouroB Fetch node (contract in `node/v0.1.json`). AC: a KouroB path with a Fetch hop validates and traces.
- T-13 (M, P2): `as_of` replay and revision webhooks. AC: same query with `as_of` returns byte-identical data and envelope hash.

**kourob/**
- K-01 (M, P0b): scaffold from section 8; CLAUDE.md; ADR-0001 (what a node is), ADR-0002 (Python node runtime on VPS as the hot-path exception), ADR-0003 (no NL entry in v0). AC: fresh-agent test.
- K-02 (M, P0b): `lib/` shared node components (validator, memo, calibrator, escalation, trace, drift sampler). AC: 100% of components unit tested; memo cleared on version bump.
- K-03 (L, P0b): `maude.dedup` node: contract, adapter, gold pairs from the MAUDEScope spec 5.11, SEEDED with teacher, then SHADOW. AC: section 10 gates for 0b.
- K-04 (M, P1): exact memo and class memo in `api/`. AC: hit-rate metric published; hash canonicalization tested against key order and whitespace.
- K-05 (M, P1): planner with hard budget, queued misses, `considered_and_rejected`. AC: budget exhaustion returns 202 with ETA; no frontier call escapes the budget guard.
- K-06 (S, P1): trace corpus on R2/JSONL, append-only, `trace/v0.1.json`. AC: every served request has a trace; CI fails a response without one.
- K-07 (M, P1): `make eval`: node-vs-gold, node-vs-teacher, calibration, path compounding loss. AC: byte-reproducible on a pinned trace set.
- K-08 (M, P2): referral handling and path patching. AC: a referral produces a new graded path within one planner cycle.
- K-09 (L, P2): collapse trainer and shadow cutover. AC: section 3.5 thresholds enforced from `config/thresholds.yaml`.
- K-10 (M, P2): codify step (rule/table extraction) for near-deterministic nodes. AC: table matches model on gold at ≥ 0.995.
- K-11 (M, P2): Thompson sampling over up to three paths per class. AC: exploration floor 5%; arm scores published.
- K-12 (M, P2): `trooth.route` distilled from Trooth resolve logs. AC: agreement with lookup ≥ 0.98; cost lower.
- K-13 (S, P2): split/merge proposals from the archivist. AC: proposals are PRs with the confusion evidence attached; never auto-merged.

**modafied/**
- M-01 (M, P1): scaffold; move Trooth `jobs/score` into `scoring/`; `make score --snapshot <id>` byte-reproducible. AC: M1 enforced in CI.
- M-02 (S, P1): anchor registry with `anchor/v0.1.json`; NWS observations, USGS revised magnitudes, BLS official releases, MAUDE gold pairs as the first four. AC: every accuracy figure on the site links an anchor.
- M-03 (M, P1): node and path scorecards from KouroB traces and evals. AC: compounding loss computed and shown per path.
- M-04 (M, P2): replica runbook and attestation format; run one replica on a second host. AC: two hosts, same snapshot, same hash.
- M-05 (S, P2): dispute process: template, reproduction requirement, public log. AC: a synthetic dispute round-trips.
- M-06 (S, P2): gold-set rotation and the seen-gold regrade rule. AC: rotation is mechanical and logged.
- M-07 (S, P1): conflict policy page: M2, the fixed transfer from Trooth, who may fund what. AC: page exists before any scorecard is public under the Modafied name.

---

## 12. Failure modes and kill rules

| Failure | Design answer |
|---|---|
| Error compounding across hops | Hop budget; typed payloads; aggressive collapse; compounding loss published per path |
| No credit assignment | Per-hop gold where an anchor exists; sampled frontier adjudication with blame vectors, offline |
| Stale memoized paths | Paths carry the schema versions they were planned against; any schema change in a member invalidates them |
| Planner cost overrun | Hard budget, queued misses, honest 202; never silent fallback |
| Injection via node or upstream text | H5 extended; typed only; quarantine and mark |
| Grader capture | Open code, byte reproducibility, replicas, M2, published fixed transfer, no overrides |
| Metric gaming by providers | Mutually constraining dimensions; rotated gold; "unmeasured" listing for refusers |
| Scope creep into "a network" | Invited contributors only until Phase 4; gates enforced; fewer nodes is the goal |

**Kill and pivot rules.**
- Repetition rate under 20% on the Phase 1 workload: freeze KouroB, keep Trooth and Modafied as benchmark plus pipe at under 10 USD/month, write the retrospective.
- First collapse does not reach 3x at equal accuracy: drop the multi-hop structure, ship nodes as standalone distilled models with scorecards. Still a business.
- Modafied cannot be kept independent: publish scores only for sources Trooth does not resell and say so on the method page.
- Replicas disagree and the cause is not a bug within 30 days: the method is not reproducible; freeze scorecard publication until it is.

---

## 13. Open decisions for Alex

1. Names. "Trooth" still promises more than the product claims. "Modafied" needs a check that it reads as a grader rather than a modification service, and a trademark search.
2. Modafied's legal shape: separate company with a published conflict policy, or a foundation-style project. Section 5.4 works either way; the choice affects who can fund it.
3. The published fixed transfer from Trooth to Modafied for public scorecard compute. A number, not a formula.
4. Which workload is instrumented first for repetition rate. 10xAnd tool traffic is the obvious candidate.
5. Whether `maude.dedup` ships under 10xAnd, KouroB, or both with cross-credit.
6. Who labels the per-hop gold sets and by when (the India team is the assumed answer).
7. Take rate and payout cadence for providers (Phase 3 ADR).
8. Which single external developer to recruit for the Phase 1 desirability gate, and which provider for Phase 3.
9. Whether access credits are worth building at all, or whether distribution plus payout is enough.

---

## 14. Revisit when

- A permissionless training run lands within 10x of frontier compute, or cheap verification of large-model inference ships: reconsider the rejected decentralization items.
- Repetition rate exceeds 80%: promote planner distillation.
- A paying customer contractually requires on-chain anchoring beyond OpenTimestamps: reopen the chain decision.
- A collapsed node underperforms its path twice in a row: the thresholds are wrong, not the concept.
- Three independent replicas agree for 90 days: consider dropping Trooth's transfer to Modafied and funding replicas by sponsorship instead.
- A provider asks to be graded before being asked: the credential incentive is working; move the provider tooling up.
