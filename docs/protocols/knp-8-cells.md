# KNP-8: Cells — containment, membrane, and division

Status: draft · Milestone: M2–M5 · Depends on: KNP-0 · Explains: all of the above

Read this first if you want the intuition. The other specs are mechanism; this is why they
are shaped the way they are.

## 1. The problem, named plainly

Building with an LLM produces unbounded growth. Every session adds: another module, another
artifact, another doc, another special case. Almost nothing is ever removed, because
removing requires knowing what is unused, and knowing that requires a record nobody kept.

The symptoms are familiar and measurable. A `tennis-predict` at 750 MB, nearly all of it
`artifacts/`. A context window that no longer fits the part of the project you need to
change. An agent that has to be told, every session, which of nine similar files is the live
one. Onboarding cost that rises until the project is effectively write-only.

This is not the model's failure. It is that **nothing in a normal project bounds what a unit
of work may touch, or tells a component that it is full.** Growth is the default and the
only default.

A cell is the unit that has both bounds.

## 2. The cell

A cell is a node, seen from the inside. Same folder, same manifest, same ledger — but with
three properties that are about *building* it rather than running it:

### 2.1 A cell is one agent's entire working set

An agent tending cell A sees A: its manifest, schemas, pages, events, tools, tests, and
handoffs. It does not see cell B. It reaches B the way any caller does — over the wire, with
a scope check, a receipt, and a price.

This is the containment that matters for development. Context is bounded **by construction**
rather than by discipline, and "discipline" is exactly what fails at 3am in session forty.
If the pack for a task does not fit, the answer is never "summarise harder". It is that the
cell is too big, and it should divide before the code is written.

### 2.2 The membrane: nothing crosses by import

Everything that crosses a cell boundary is **typed** (an ODCS schema), **metered** (a
receipt), and **declared** (in scope). Nothing crosses by `import`.

> **No cell imports another cell's code.** Not a convenience helper, not a shared constant,
> not "just the types". CI enforces it.

This is the rule people will most want to break, and breaking it is how a set of cells
silently becomes one large program with extra ceremony. A shared import is an undeclared,
unmetered, untyped dependency: it does not appear in any route table, no receipt records it,
and it cannot be versioned, priced, or refused.

The cost is real — some duplication across cells, and a wire hop where a function call would
do. That cost buys the ability to change, split, shed, or delete any cell without reading
any other, which is the only property that makes a large system tractable to an agent.

### 2.3 A cell has a size ceiling, not a size target

```yaml
# kourob.yaml
cell:
  max_context_tokens: 15000     # a task pack must fit. The binding constraint
  max_source_files: 40
  max_source_lines: 4000
  max_schemas: 3
  max_tiers: 4
  max_hot_storage_mb: 500       # cold-stored partitions are exempt
  max_tools: 8
  on_exceed: propose_division   # propose_division | halt | warn
```

`max_context_tokens` is the one that does the work; the others are proxies for it that can
be checked without building a pack.

**Exceeding the ceiling does not grow the ceiling.** A PR that pushes a cell over budget
fails CI. The cell must shed (KNP-5 §6) or divide (§3) first. Raising a limit is a manifest
change, which is a human decision with a diff, and it should feel like one.

## 3. Division

A cell does not get bigger. It divides.

There are two pressures, and they produce the same operation:

| Pressure | Signal | Spec |
|---|---|---|
| **Demand** | `demand_factor` over `split_threshold` for `split_window`, and ≥2 clusters over `min_cluster_share` on disjoint schemas or tools | KNP-5 §7 |
| **Size** | any `cell.max_*` exceeded | this spec |

### 3.1 Division happens along a seam

A cell may only divide along a **seam**: a set of schemas or tools with no shared writes and
no shared rules. Seams are found, not chosen — the evolve loop looks for the minimum cut in
the graph of (schema, tool, rule) co-occurrence across the request log.

If no seam exists, the cell **cannot divide**, and that is the interesting case: it means the
cell is genuinely one indivisible thing that is too large. That is a design error, and
`tend` escalates it to a human rather than cutting somewhere arbitrary. An arbitrary cut
produces two cells that call each other constantly, which is worse than one large cell —
you have paid every cost of division and bought none of the isolation.

### 3.2 What a division carries

The child gets its clusters' schemas, tiers, rules, gold, and hot partitions. **It inherits
the parent's promotion state** — a child does not relearn what the parent already distilled.
The parent narrows its declaration, deletes what it gave away, and gains a referral rule.

Both publish to the set registry, because routing changed and everyone pointing at the
parent needs to learn the new shape (KNP-7 §6).

### 3.3 Death

The inverse also has to exist or the set only ever accumulates. A cell is retired when it is
`failing` past its bootstrap grant (KNP-7 §3), or when shedding has reduced it to nothing it
still serves. Retirement: freeze the ledger, cold-store the events, publish a tombstone in
the registry naming the successor if there is one, and leave the receipts verifiable
forever.

**A retired cell's answers stay traceable.** That is the whole reason the ledger is
append-only and retention for receipts is `forever`: work that has been deleted must still be
explicable.

## 4. Contact: cells that touch

Two cells touch when one routes to the other, or one consumes a schema the other publishes.
The contact surface is exactly four things, all of them already published:

| | Where | What changes on the other side |
|---|---|---|
| **schema version** | set registry, ODCS contract | Consumer invalidates every rule and student reading it. No grace period (KNP-5 §5) |
| **scope declaration** | agent card, `ext/scope/v1` | Consumer's route table entry narrows or drops |
| **price and ceiling** | agent card, `ext/meter/v1` | Consumer's payback and quote maths change (KNP-5 §4) |
| **autonomy level** | set registry | Consumer knows how autonomously its upstream is changing. A4 is a different counterparty from A0 |

Nothing else is a contract. A neighbour's file layout, module names, model choice, tier mix,
internal rules and storage backend are all free to change without notice, because none of
them crosses the membrane.

**This is what "supports the cells touching it" means concretely**: a cell's obligation to
its neighbours is to keep those four things honest and to announce changes to them. It has
no obligation to keep anything else stable, and it should feel free to rewrite its own
insides entirely — which is precisely the freedom that lets it be tended by an agent.

## 5. Developing a cell with an agent

The rules that keep a project from exploding, in the order they bind:

1. **One task, one cell, one branch, one worktree.** An agent's working directory is the
   cell. Nothing above it is on the path.
2. **The pack must fit.** `kourob pack <task>` builds the agent's context from the cell's
   manifest, its scope, the relevant pages with their citations, the schemas touched, and
   the last three handoffs. If it exceeds `max_context_tokens`, **stop and divide.** Do not
   summarise, do not "just this once" — a pack that does not fit is the earliest and
   cheapest signal that the cell is too big, and it arrives before any code is written.
3. **CI enforces the ceiling.** A PR that pushes any `cell.max_*` over budget fails. The
   fix is a shed or a division, not a raised limit.
4. **No cross-cell imports.** CI greps for them.
5. **Deletion is normal work.** `prune` and shed proposals are first-class output of `tend`,
   not cleanup somebody gets to eventually. A cell that only ever grows is failing at its
   job even when its answers are fine.
6. **Every session ends with a handoff.** The next agent starts from the record, not from
   re-reading the code.

Points 2 and 3 are the load-bearing ones and they are what this project has that a normal
repo does not. Everything else is good practice that erodes; those two are checks that fail.

## 6. Why cells and not services, packages, or modules

The comparison is worth being explicit about, because the shape looks familiar.

| | Bounded context | Metered | Provenance | Self-modifying | Divides on pressure |
|---|---|---|---|---|---|
| Module | no — imports cross freely | no | no | no | no |
| Package | at build time | no | no | no | no |
| Microservice | yes | rarely | no | no | manually, at great cost |
| **Cell** | yes | yes | yes | yes, within KNP-7 | yes, automatically proposed |

A microservice is the closest neighbour and gets the first two columns for free. The
difference is the last three: a service does not know what it cost, cannot explain where its
answer came from, does not improve itself, and grows until a human reorganises it. A cell's
whole point is that those four are mechanised, so that the thing tending it can be an agent
running on a schedule rather than a team.

## 7. Falsifiable claims

1. A task pack for any cell in `examples/` fits `max_context_tokens`.
2. No module in any cell imports from another cell.
3. A cell driven past `max_source_lines` by synthetic growth proposes a division along a
   real seam, not an arbitrary cut.
4. A cell with no seam and over budget halts and escalates rather than dividing.
5. A retired cell's receipts still verify and its answers still trace.

Claims 3 and 4 are the ones that decide whether "divide instead of grow" is a mechanism or a
slogan.
