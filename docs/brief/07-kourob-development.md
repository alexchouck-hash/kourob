# KouroB: A Network of Self-Specializing Nodes

**Status:** development brief v0.1, September 2026. This file is written to be handed to Claude Code as the first input for the repository. Read it fully before writing any code. Section 0 tells you how to work from it.

**One paragraph.** KouroB is an open-source structure for building nodes: small, specialized, metered units of knowledge and capability that other builders can create, connect, and chain into products. A node owns a slice of the world (typed events, compiled knowledge, tools, provenance), serves requests through standard ports, and evolves toward whatever is pulled from it. Frontier LLMs train nodes; nodes then serve far more cheaply than an LLM would. Out-of-scope requests are refused or referred to another node. Every request leaves a signed receipt, so provenance and cost are traceable across chains of nodes, and callers learn the shortest, cheapest path over time. Nodes under high demand price up and split into more specialized children. The project is a series of nodes and node sets that interconnect; users reach them through chains of nodes ending in whatever UI they like.

Supersedes `06-ourob-development.md`. Builds on `01` (repo as memory), `02` (distillation), `03` (own data and tools), `04` (event-sourced streams), `05` (the harness).

---

## 0. How to work from this document (instructions for Claude Code)

1. Create the repository skeleton in section 11 exactly, including `AGENTS.md` from section 13. `CLAUDE.md` is a one-line pointer to `AGENTS.md`.
2. Work milestone by milestone from section 12. Each milestone lists acceptance criteria; turn each criterion into a test before writing the implementation.
3. Every design choice marked **ADR** in this document gets a file in `docs/adr/` before implementation. Use the template in section 13.4. Do not implement an alternative silently.
4. Where this document says "v1" it means the minimum that makes the milestone's tests pass. Do not build for scale in v1; build the contract and the tests, then the simplest implementation.
5. Anything not specified: check `docs/DEFAULTS.md` (you will write it in M0 from section 13.3), decide, record the decision in the PR under `## Decisions made without asking`, and continue. Escalate to the human only on the criteria in section 13.3.
6. Session start and end rituals in `AGENTS.md` are mandatory. Write a handoff file every session.
7. KouroB dogfoods itself: the repo is the first node. Once M2 passes, the project's own docs must be served by a KouroB node in `examples/kourob-node/`.

---

## 1. Goal

> Any builder can create a node in one command, connect it to other nodes, and have it become cheaper and better at its job with every request it serves, while every answer it gives can be traced back to its sources and its cost can be metered along the whole chain that produced it.

Measurable targets for v1.0:

| Metric | Target |
|---|---|
| Time from `kourob init` to a node answering over MCP with a cited answer | Under 10 minutes |
| Share of requests served by tier 0 or 1 (rules, cache, distilled model) after 30 days of traffic on the example node | 80 percent or more |
| Cost per request on the example node, day 30 vs day 1 | Down 5x or more |
| Provenance: fraction of answers whose full chain (every node, every source, every model version) is reconstructible from receipts | 100 percent |
| Referral learning: second request for the same out-of-scope topic goes direct (no bridge hop) | Yes, measured by the router test |
| Split: a node receiving a bimodal request distribution auto-proposes a split within one evolve cycle | Yes, measured by the split test |

---

## 2. Vocabulary

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

---

## 3. The node

```
                 ┌────────────────────────────────────────────┐
   in-ports ───▶ │ scope check ─▶ gate ─▶ tiers ─▶ receipt     │ ───▶ out-ports
   (MCP, A2A,    │                  │        │        │        │      (MCP, A2A, REST,
    REST, files, │              events   knowledge  ledger     │       events, exports,
    git, email)  │              store    (pages)   (receipts)  │       referrals)
                 │                     ▲                       │
                 │        evolve loop ─┘ (reads log + receipts,│
                 │        retrains tiers, proposes splits)      │
                 └────────────────────────────────────────────┘
```

### 3.1 Request handling, in order

1. **Authenticate and meter-check.** Caller presents a key (node keypair or user token). Check credit balance or free-tier allowance.
2. **Scope check.** Is this request inside declared scope? Three outcomes: `in_scope`, `out_of_scope_referral` (with candidate node ids from the route table), `out_of_scope_reject` (no known node).
3. **Gate** (for writes/pushes). Stamp, validate against schema, dedupe, classify PII/consent, threshold on novelty. Route to silver or quarantine. Emit events for what fired.
4. **Tier selection** (for reads/pulls). Try T0 (exact match in cache, SQL over silver, rule). If confidence below bar, T1 (distilled model). If still below, T2, then T3. T4 (human review queue) only for tools flagged `review_required`. Every tier attempt is logged.
5. **Answer.** Structured `data` plus `rendered` markdown plus `citations` (event ids) plus `receipt_id`.
6. **Receipt.** Sign and append to the ledger. Include upstream receipt ids if other nodes were called.
7. **Log.** The request, the tiers tried, the latency, and the cost go to the request log, which is itself a dataset the evolve loop reads.

### 3.2 Bridging

When a node refers out, it may bridge instead:

```
caller ──▶ node A (out of scope, knows node B) ──▶ node B ──▶ answer + receipt_B
      ◀── answer + receipt_A(upstream: receipt_B) + route_hint: {node: B, scope: ..., cost: ...}
```

The caller stores the route hint in its own route table. Next time it goes straight to B. Node A bridges the same (caller, scope) pair at most `bridge_limit` times (default 3), then refers only. This is how the network finds shorter, cheaper paths: not by a global optimizer, but by every node learning from receipts it has seen.

### 3.3 Why a node is cheaper than an LLM

An LLM answers every question from scratch with billions of parameters. A node answers most questions from T0 (a lookup or a rule) or T1 (a model with a few million parameters trained on this node's exact request distribution). The frontier model is used to build those tiers, not to run them. Cost per request therefore falls as the node ages, and the request log tells the trainer exactly what to distill next. The node is not a smaller LLM; it is a compiled artifact of what an LLM figured out about one narrow job, plus the data that job needs.

---

## 4. Provenance and metering: the ledger

### 4.1 Receipt (v1 schema)

```yaml
receipt:
  id: rcpt_01J...                # ULID
  node: did:key:z6Mk...          # node identity
  caller: did:key:z6Mk... | user:...
  request_hash: sha256:...
  response_hash: sha256:...
  scope_result: in_scope | referral | reject | bridge
  tier_used: T0 | T1 | T2 | T3 | T4
  model_version: student-s@0.4.2 | frontier:<vendor>:<model> | rule:<id>
  citations: [evt_..., evt_...]
  upstream: [rcpt_...]            # receipts from other nodes this answer depended on
  cost_credits: 0.0031
  price_credits: 0.005
  ts: 2026-09-09T21:04:11Z
  prev: sha256:<previous receipt hash>   # hash chain per node
  sig: <ed25519 signature over all fields above>
```

### 4.2 Ledger design (**ADR-0003**)

- **v1:** per-node append-only receipt log, hash-chained, ed25519-signed with the node's key. Stored as Parquet, exported as JSONL. `kourob ledger verify` walks the chain and checks every signature.
- **v1.1:** periodic Merkle root of each node's ledger published to the set's registry, so a set operator cannot silently rewrite a node's history. This is the transparency-log pattern (Certificate Transparency, Sigstore's Rekor). Evaluate Trillian or a simple Merkle tree library.
- **Later, optional, off by default:** anchor set-level Merkle roots to a public chain for trustless auditability between operators who do not trust each other. Evaluate only when cross-operator settlement exists.

**On blockchain, honestly:** a blockchain buys you two things: tamper-evidence between parties who do not trust each other, and settlement without an intermediary. Neither is needed while all nodes belong to one operator or a few cooperating ones. Signed hash chains plus Merkle anchoring give tamper-evidence at near-zero cost and complexity. When cross-operator payment is real, evaluate HTTP-native payment protocols (x402-style HTTP 402 flows, L402/Lightning) before a custom chain. Write this as ADR-0003 and revisit when there are three or more independent operators.

### 4.3 Provenance graph

Receipts plus event provenance stamps form a directed acyclic graph: answer → receipts → events → sources (and upstream receipts → other nodes). `kourob trace <receipt_id>` renders the full chain. Use W3C PROV vocabulary (entity, activity, agent, wasDerivedFrom, wasGeneratedBy) for the export format so external tools can read it. Every page in the knowledge base cites event ids, so a human reading a page can trace any sentence the same way.

### 4.4 Metering

- Every receipt records `cost_credits` (what it cost the node: model tokens, compute, upstream node prices) and `price_credits` (what the caller was charged).
- Balances live in `ledger/accounts.parquet` in v1. Callers get a free allowance per manifest.
- Price is a function the node computes, see section 5. Cost is measured, not estimated: the runner logs actual token counts per tier.
- `kourob meter report` shows revenue, cost, margin, and top callers per period.

---

## 5. Economics: pricing, splitting, sizing

### 5.1 Price function (**ADR-0004**)

```
price = base_cost(tier_used) * (1 + demand_factor) * quality_multiplier
demand_factor = clamp((requests_last_window / capacity_window) - 1, 0, max_surge)
```

Price rises with load. This does two things: it rations the node and it funds the split. The manifest declares `capacity_window` and `max_surge`. Callers see the current price in the agent card before they call.

### 5.2 Auto-split (**ADR-0005**)

The evolve loop clusters the request log (by scope classifier labels, schemas touched, tools called). A split is proposed when:

- demand_factor has exceeded `split_threshold` for `split_window`, and
- the request distribution has at least two clusters, each above `min_cluster_share`, that touch mostly disjoint schemas or tools.

A split creates a child node with a narrowed scope, copies the relevant events and pages, trains the child's tiers on the cluster, and adds a referral rule in the parent. The parent's scope shrinks or the parent becomes a pure router. Splits are proposed as a PR with the evidence; the human (or a policy in DEFAULTS.md) approves. Merges are the inverse and run when two siblings are both under-utilized.

### 5.3 Optimal sizing

A node's size is the sum of its tiers, its silver data, and its pages. The evolve loop keeps it minimal for its request distribution:

- Tiers: distill down while quality holds (T3 → T2 → T1 → T0 rules where patterns are deterministic). Re-measure against gold after every step.
- Data: bronze expires per retention; derived is rebuilt on demand; silver is partitioned so cold partitions can move to cheaper storage.
- Pages: compaction summarizes rarely-pulled pages and keeps them regenerable from events.

The signal for all of this is the request log. A node with no requests for a schema does not keep a tier for it.

---

## 6. Learning: how a node evolves toward its pulls

### 6.1 Loops (each is a scheduled job with a budget and a PR or an event as its only output)

| Loop | Trigger | Reads | Changes |
|---|---|---|---|
| ingest | inbox, webhook, cron, git push | sources | events, quarantine |
| compile | events fired | events | pages, index |
| lint | nightly | pages, events, tasks | flags (contradiction, uncited claim, stale, orphan task, schema drift) |
| **evolve** | weekly, or on demand_factor breach | request log, receipts, quarantine | proposes: new T0 rules, T1 retrain, scope changes, split/merge, new tools, DEFAULTS changes |
| distill | evolve proposes it | call log, gold | trained student, cascade thresholds, registry entry |
| prune | weekly | retention policy, usage | deletions, compaction |
| reflect | weekly | everything above | one digest PR for the human |

### 6.2 Trainers

A trainer is a frontier-model session with a fixed brief: create a node from a scope description and seed data, or improve one from its evolve report. Trainers write schemas, gold sets, scope rules, few-shot sets for T2, and run `kourob distill`. Trainer sessions are expensive and logged as such; their cost is amortized in the node's price over time. `kourob train <node> --brief <file>` launches one with the vendor-neutral runner.

### 6.3 What "each pull leaves the node more useful" means concretely

- A pull that hit T3 becomes a labeled example for T1. Enough of them and T1 learns it.
- A pull that was referred out records the route; the next caller gets a direct referral.
- A pull whose answer was corrected (correction event) re-weights the source and retrains.
- A pull that hit T0 refreshes the cache and increments the usage counter that protects that rule from pruning.
- A push that passed the gate adds an event, recompiles a page, and may fire downstream.
- A push that failed lands in quarantine, and repeated quarantine reasons become schema or rule proposals in the next evolve.

---

## 7. Routing and chains to UI

- Every node keeps `routes.parquet`: (scope pattern, node id, observed price, observed latency, last success, source receipt). Learned from referrals, bridges, and the set registry.
- A **set registry** is a signed list of nodes, their scopes, agent cards, and Merkle roots. Sets can peer with other sets by exchanging registries. No global registry in v1.
- **Chains to UI:** a UI is just another caller. A user's assistant (Claude, a web app, a phone app) calls the nearest node; that node answers or refers; the chain resolves in a few hops; the UI renders `rendered` or builds its own view from `data`. Ship one reference UI (`examples/ui/`) that is a thin client over a node's REST port and can be regenerated by any agent.
- Loop prevention: requests carry a hop list; a node refuses a request whose hop list already contains it. Max hops in manifest.

---

## 8. What a node is, on disk

```
my-node/
  kourob.yaml                  manifest: identity, scope, ports, tiers, pricing, loops, retention
  GOAL.md                      one paragraph
  AGENTS.md                    for agents attached to this node (generated, editable)
  schemas/                     ODCS contracts (*.odcs.yaml) → generated pydantic in .kourob/gen/
  data/
    bronze/  silver/  gold/  quarantine/  derived/   manifest.yaml
  pages/                       compiled knowledge (markdown, cited), index.md
  tools/                       tool definitions (schema, scope, dry_run, review_required, audit)
  tiers/
    t0/rules/                  deterministic rules and SQL views
    t1/                        distilled model weights or pointer, calibration, thresholds
    t2/  t3/                   prompts, few-shot sets, model selection
  ledger/
    receipts.parquet  accounts.parquet  merkle/
  routes.parquet
  logs/requests.parquet  calls.parquet
  docs/adr  docs/experiments  docs/handoffs  docs/DEFAULTS.md
  .kourob/                     keys (gitignored), gen/, cache/
```

A node is a git repo. Events, pages, schemas, rules, and receipts are versioned; weights and bronze go through DVC.

---

## 9. Stack decisions for v1

| Concern | Decision | Why |
|---|---|---|
| Language | Python 3.12, `uv`, `ruff`, `pytest` | Agents and the data ecosystem live here |
| Schemas | ODCS contracts via `datacontract-cli`; pydantic v2 generated | Vendor-neutral standard, breaking-change detection, exports |
| Event store | Parquet + DuckDB, append-only, partitioned by month | Zero infrastructure; SQL everywhere. **ADR-0001** keeps a `Store` interface so Dolt or Postgres can be swapped in |
| Data versioning | DVC for bronze and weights | Repo-scale, already stewarded |
| Tasks | Beads (`bd`) via a thin adapter | Git-backed task graph with atomic claims and compaction; do not rebuild |
| Agent-to-tool port | MCP, official Python SDK | Primary attach surface |
| Node-to-node port | A2A (a2a-python SDK), agent card at `/.well-known/agent.json` extended with KouroB scope, price, and Merkle root | Linux Foundation standard; extension fields are namespaced `kourob.*` |
| REST | FastAPI, OpenAPI generated | UI and scripting |
| Events out | SSE + webhooks, CloudEvents envelope, payload is an ODCS-typed event | Interop with buses later |
| Identity and signing | ed25519 keypairs, `did:key` ids | No registry needed to verify |
| Ledger | Hash-chained signed Parquet; Merkle roots in v1.1 | Section 4.2 |
| Distillation | Unsloth or HF PEFT for LoRA on 0.5B to 3B open models; sklearn or a small torch head for tabular; ONNX export | Doc 02 |
| Scope classifier | Rules + a T1 classifier trained from the request log | Cheap, explainable |
| Runner | `kourob run` with adapters: claude_code, codex, openai, anthropic, gemini, local (ollama/vllm) | Vendor neutral |
| Docs | MkDocs Material over `pages/` | Human view |
| CI | GitHub Actions: tests, contract lint, ledger verify, gold isolation check, loops on cron | |
| License | Apache-2.0 (**ADR-0002**) | Patent grant; matches Beads, A2A, Dolt |

---

## 10. Prior art (condensed from 06; verified September 2026)

Build on: Beads (task graph, claims, compaction), Karpathy's LLM-wiki pattern and llm-wikid (compile and lint), datacontract-cli/ODCS (schemas), MCP and A2A (ports), DVC (versioning), DuckDB/Parquet (store).
Borrow: Gas Town (role separation, merge-queue agent, worktree persistence), Graphiti (bi-temporal facts), Cognee (retrieval backend when grep over pages stops scaling), OpenLineage and W3C PROV (provenance vocabulary), Certificate Transparency / Rekor (ledger design).
Avoid as core: chat-memory products (Mem0, Letta, Hindsight), vector databases in v1, any UI framework as a product.
Name check: `KouroB` has no collision found; `ouroboros` is heavily used (razzant/ouroboros is a self-modifying agent; Cardano's networking stack). State in the README that KouroB is a node network, not an agent.

---

## 11. Repository layout (create this in M0)

```
kourob/
  README.md                    what it is in five lines; one-command demo; what it is not
  GOAL.md                      section 1 of this document
  AGENTS.md                    section 13
  CLAUDE.md                    "Read AGENTS.md"
  LICENSE                      Apache-2.0
  pyproject.toml               package `kourob`, CLI entry `kourob`
  docs/
    brief/                     this file and 01 to 05, unchanged, as source material
    adr/  experiments/  spikes/  ideas/  handoffs/  decisions/  runbooks/
    DEFAULTS.md  GLOSSARY.md  ARCHITECTURE.md (generated)
  src/kourob/
    cli.py
    manifest.py
    identity.py                keys, did:key, signing
    schema/                    odcs loader, codegen, versioning, breaking-change check
    store/                     Store interface; parquet_duckdb backend
    events.py                  event model, provenance stamp, novelty
    gate.py                    stamp → parse → validate → dedupe → classify → threshold → route
    scope.py                   scope declaration, rule classifier, T1 classifier hook
    tiers/                     base Tier, T0Rules, T1Student, T2Mid, T3Frontier, T4Human, cascade
    knowledge/                 compile pages from events with citations; index; backlinks
    tools/                     registry, dry-run, audit, review gate
    ledger/                    receipt model, hash chain, signing, verify, merkle (v1.1), accounts, pricing
    routes.py                  route table, referral, bridge, hop list
    ports/                     mcp.py a2a.py rest.py events.py files.py git.py
    loops/                     ingest.py compile.py lint.py evolve.py distill/ prune.py reflect.py
    trainer/                   briefs, train.py
    runner/                    run.py, adapters/
    pack.py                    context packs for attached agents
    tasks.py                   Beads adapter
  template/                    what `kourob init` lays down (section 8)
  examples/
    kourob-node/               the project's own docs as a node (dogfood, M2)
    tennis-node/               Match Charting → shot.v1 (M3)
    ui/                        reference thin client (M5)
  evals/
    fresh_agent_test.py  gate_fixtures/  router_test.py  split_test.py  cost_curve.py
  tests/
  .github/
    workflows/ci.yml  loops.yml
    CODEOWNERS  PULL_REQUEST_TEMPLATE.md  ISSUE_TEMPLATE/task.md
```

---

## 12. Milestones

Each milestone is a GitHub milestone. Each bullet under "Acceptance" becomes a test or an eval before implementation starts. Estimates assume one human reviewing and several agent sessions per day.

### M0: Skeleton and conventions (week 1)
Deliver: layout in section 11, `AGENTS.md`, `DEFAULTS.md`, ADR template, PR template, CI running `ruff` and `pytest`, Beads initialized, ADR-0001 (store interface), ADR-0002 (license).
Acceptance:
- `uv run kourob --help` lists all top-level commands as stubs.
- CI green on an empty test suite plus lint.
- `bd ready` returns the M1 tasks.

### M1: A node that ingests and answers (weeks 2 to 3)
Deliver: manifest, identity, ODCS schema loading and codegen, Parquet/DuckDB store, gate with quarantine, events with provenance, T0 (SQL and rules) and T3 (frontier) tiers with cascade, receipts with hash chain and signatures, MCP port with `query`, `ingest`, `get_page` (page returns raw event list in M1), `list_schemas`.
Acceptance:
- `kourob init demo && cd demo && kourob ingest fixtures/events.jsonl` produces silver rows and a quarantine file with reasons for the malformed fixtures.
- Gate fixture eval: precision and recall of rejections ≥ 0.95 on `evals/gate_fixtures/`.
- Every answer over MCP includes `data`, `rendered`, `citations`, `receipt_id`.
- `kourob ledger verify` passes; tampering with one receipt in the fixture ledger makes it fail.
- A T0-answerable question never reaches T3 (assert via receipt `tier_used`).

### M2: Knowledge, packs, attach, dogfood (weeks 4 to 5)
Deliver: compile loop (pages from events, citation on every claim), lint loop, `kourob attach claude-code|codex|cursor`, context packs, `examples/kourob-node` serving this repo's docs.
Acceptance:
- Lint fails on a page containing an uncited claim (fixture).
- Fresh-agent test: a new Claude Code session attached to `examples/kourob-node` answers "what is a bridge and when does a node stop bridging" with a citation, without asking the human, in under 10 minutes.
- Pack size for a sample task under 15k tokens; measured and logged.

### M3: Node-to-node: A2A, referral, bridge, routes (weeks 6 to 7)
Deliver: A2A port with extended agent card, scope classifier (rules), referral and bridge, route table, hop list, `examples/tennis-node` on Match Charting data, `kourob attach <node-url>`.
Acceptance:
- Router test: node A (kourob-node) receives a tennis question; first call bridges to tennis-node and returns `route_hint`; second call from the same caller is refused with a referral; the caller's route table now points at tennis-node directly.
- A request whose hop list contains the node is refused.
- `kourob trace <receipt_id>` on the bridged answer shows both nodes, both receipts, and the events cited.

### M4: Metering, pricing, evolve, split (weeks 8 to 10)
Deliver: accounts, price function, `kourob meter report`, request log as a dataset, evolve loop (rule proposals, T1 retrain trigger, split proposal), Merkle roots (v1.1 ledger), ADR-0003, ADR-0004, ADR-0005.
Acceptance:
- Price rises monotonically with simulated demand above capacity and returns to base when demand falls (unit test on the price function with a synthetic request log).
- Split test: a synthetic bimodal request log over two disjoint schemas produces a split proposal PR with a child manifest, a narrowed parent scope, and a referral rule.
- Merkle root of a node's ledger verifies against the set registry; altering a receipt breaks it.

### M5: Distill and cost curve, reference UI (weeks 11 to 13)
Deliver: T1 tier with training from the call log (scope classifier first, then the ingest classifier), cascade thresholds calibrated on gold, `kourob distill` commands, `examples/ui`, `kourob publish`.
Acceptance:
- Cost-curve eval: replaying 30 days of synthetic traffic on tennis-node, cost per request on day 30 is at most one fifth of day 1, and T0+T1 share ≥ 80 percent.
- Student vs gold accuracy within 2 points of the teacher on the scope classifier.
- The reference UI renders a node's answer from REST with no node-specific code.

### v1.0: tag when M0 to M5 pass, docs are served by kourob-node, and `pipx install kourob` works from PyPI.

---

## 13. Conventions (this becomes `AGENTS.md`)

### 13.1 What this project is
KouroB is a Python package and template for building metered, provenance-tracked, self-specializing nodes that agents and other nodes attach to through MCP, A2A, and REST. The repo is the first node. Read `docs/brief/07-kourob-development.md` for the full design.

### 13.2 Session rituals
Start: read `AGENTS.md`, `GOAL.md`, `docs/DEFAULTS.md`, the claimed Beads task (`bd show <id>`), the last three files in `docs/handoffs/`; grep `docs/adr`, `docs/experiments`, `docs/spikes` for the task's keywords and list what you found in the PR description before writing code; state the plan in the PR.
End: write `docs/handoffs/YYYY-MM-DD-<agent>-<task>.md` (done, not done, surprises, open questions, exact resume commands); write an experiment entry for anything tried and abandoned; write or update an ADR for any decision; `bd close` or `bd update`; open a PR; never merge your own work.

### 13.3 Decide, do not ask (`docs/DEFAULTS.md`, initial content)
- Naming: snake_case Python, kebab-case files and CLI flags, ISO 8601 UTC timestamps, ULIDs for ids.
- New dependency: allowed if permissive license and under 5 MB installed; note it in the PR. Otherwise ADR.
- Tests: pytest; every acceptance criterion in section 12 is a test; fixtures in `tests/fixtures/`; no network in unit tests.
- Ambiguous spec: choose the stricter reading, record it under `## Decisions made without asking`.
- Schema changes: ADR first, then implement; run `datacontract changelog`.
- Model calls in tests: mocked via the runner's `local` adapter.
- Escalate to the human only when: irreversible or external side effect (deleting data, spending money, publishing), contradiction with GOAL.md or an accepted ADR, two spikes disagree on something that moves a section 1 metric, or the change touches keys, payments, or minors' data.

### 13.4 ADR template
```
# ADR-NNNN: <title>
Status: proposed | accepted | rejected | superseded-by-NNNN
Date:
Context:
Options considered:
  A. ... (spike: docs/spikes/... or "not explored because ...")
  B. ...
Decision:
Consequences:
Revisit when:
```
No option may be rejected without a spike or an explicit "not explored because" line.

### 13.5 Code rules
- Nothing writes to `data/silver` or `data/gold` except `gate.py`. CI greps for it.
- Training code never references `data/gold` paths except through `evals/`. CI checks.
- Every port handler returns `{data, rendered, citations, receipt_id}`.
- Every model call goes through `runner/` so it is logged to `logs/calls.parquet` with tier, tokens, and cost.
- Ports are thin; logic lives in `core`. A port file over 300 lines is a smell.
- Small PRs, one Beads task each, under 400 lines changed where possible. Docs-only and tests-only PRs may be auto-approved by the reviewer agent.
- Commit style: `type(scope): summary` with types feat, fix, docs, test, refactor, chore, adr.

### 13.6 Roles
Planner (turns milestones into Beads tasks with acceptance criteria and context pointers), Implementer (one task, one branch, one worktree), Reviewer (a different vendor than the implementer; may only block with a cited reason), Skeptic (attacks the design of M3 to M5 before implementation: leakage, forged receipts, route poisoning, split thrash), Archivist (weekly loops), Trainer (frontier sessions that build example nodes).

---

## 14. GitHub project setup (human does this once, or an agent with `gh` and permission)

```
gh repo create <org>/kourob --public --license apache-2.0 --description "Metered, provenance-tracked, self-specializing nodes that agents attach to"
cd kourob && git init && bd init
gh api -X PUT repos/<org>/kourob/branches/main/protection -f required_status_checks='{"strict":true,"contexts":["ci"]}' -f enforce_admins=true -f required_pull_request_reviews='{"required_approving_review_count":1}' -f restrictions=null
gh label create adr; gh label create spike; gh label create evolve; gh label create split; gh label create security
for m in M0 M1 M2 M3 M4 M5; do gh api -X POST repos/<org>/kourob/milestones -f title=$m; done
gh project create --owner <org> --title "KouroB v1.0"
```

Repo settings: squash merges only; delete branches on merge; Actions with cron enabled; Dependabot on; secrets for the loop runner's model keys stored as repository secrets and never in the manifest.

---

## 15. Risks and what is deliberately not solved in v1

- **Route poisoning.** A malicious node returns false route hints. v1 mitigates with signed receipts and set-scoped trust; cross-set trust is an ADR after three operators exist.
- **Split thrash.** Splitting and merging on noisy demand. Mitigate with hysteresis (`split_window` long, `merge_window` longer) and human approval on split PRs in v1.
- **Receipt forgery within a compromised node.** Merkle anchoring to the set registry limits the damage window; public anchoring is deferred.
- **Distilled tiers copying teacher mistakes.** Gold sets and per-class evaluation, per doc 02. A node without a gold set cannot enable T1 (enforced).
- **Privacy in receipts.** Receipts hash requests and responses; they do not store them. The request log is local to the node and subject to retention. PII classification at the gate.
- **Payment.** Credits are an internal ledger in v1. No money moves. This is intentional.
- **Scope creep.** If a proposal does not move a section 1 metric, it goes to `docs/ideas/`.

---

## 16. First session checklist for Claude Code

1. Read this file, then `01` to `05` in `docs/brief/`.
2. Create the layout in section 11. Write `AGENTS.md` from section 13, `CLAUDE.md` as a pointer, `DEFAULTS.md` from 13.3, `GOAL.md` from section 1.
3. Write ADR-0001 (store interface, Parquet+DuckDB default) and ADR-0002 (Apache-2.0).
4. `bd init`; create the M1 tasks from section 12 with acceptance criteria and context pointers; `bd ready` should list them.
5. Set up `pyproject.toml`, `uv`, `ruff`, `pytest`, CI.
6. Write the M1 acceptance tests as failing tests.
7. Open the M0 PR. Write the handoff. Stop and wait for review.
