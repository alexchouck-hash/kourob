# Self-improving nodes: where KouroB should go next

Dated 2026-09-22. This is a proposal, not a decision. It changes what `GOAL.md` measures,
so it needs a human yes before any ADR.

## Where the project stands

- About 10.6k lines, 8 KNP specs, 9 ADRs. `docs/STATUS.md` scores six of six metrics as met.
- Every one of those metrics was measured on a **synthetic replay or the local transport**.
  No outside caller has sent a request, and the Phase 1 gate in `POSITIONING.md` (25 weekly
  active callers, one external developer) is at zero.
- Today "self-improving" means three things: T0 rule mining by exact replay, a T1 that
  returns the nearest settled answer (no weights), and `tend` applying proposals within an
  autonomy budget. That is a solid safety harness around a learner that barely learns.
- **The real bottleneck is labels.** Only `note.v1` settles. T3 answers carry no
  `settle_key` (STATUS weakness #5). Probabilistic answers have no comparator, and that
  question is still waiting on a human. A node can't improve on traffic it can't grade, and
  right now the only traffic it can grade is the kind that's already cheap.

## The diagnosis

The project has built the immune system (receipts, gates, rollback, autonomy ladder)
before the organism has a metabolism (real traffic plus a label source). Three brands
(Trooth, KouroB, Modafied) and a marketing plan sit on top of a loop that has never closed
on real requests.

## The pivot: auditable self-improvement

**One sentence:** *put a KouroB node in front of any repeated tool or model call. It learns
from its own traffic to answer more cheaply, and it proves every improvement with signed
before-and-after evidence you can roll back.*

Every "self-improving agent" project gets asked the same thing: how do you know it got
better and didn't just drift? KouroB already has most of the answer: exact replay, gold
calibration, change events that carry their own inverse, and demotion after one
correction. That answer is the product. Frame the pitch around the improvement, not the
data network.

What changes:

| From | To |
|---|---|
| A node you build by ingesting events | A node you **wrap around a call** you already make (`kourob wrap <mcp-server or API>`); traffic is the dataset from minute one |
| Improvement measured on a synthetic 30-day replay | Improvement measured on **real traffic**, published as a signed improvement ledger |
| Labels only from `note.v1` reality settlement | **A label economy**: reality, caller acceptance, shadow teacher, peers |
| T1 = nearest settled answer | A learner ladder: few-shot → student model → rule, with each rung gated on gold |
| Three brands marketed together | KouroB leads; Trooth/Modafied become example integrations until the loop is proven |

## The self-improvement engine, concretely

Ordered by how much each one unblocks.

1. **Shadow teacher (the missing label source).** Under a budget, send a sample of
   T0/T1/T2 answers back to T3 off the hot path. If T3 agrees, that settles the answer. If
   it disagrees, that counts as a correction and runs the existing one-correction demotion.
   The sample rate falls as a cluster's agreement rises, so the grading cost shrinks too.
   This gives every tier a label, T3 included through cross-model agreement, with no human
   in the loop. It is a small extension of `outcomes` plus `tend`.
2. **`settle_key` on every answer, T3 included.** If there is no key, the answer can't
   improve. Fix STATUS weakness #5 first, since #1 depends on it.
3. **Improvement ledger.** Every `node_change.v1` records the cluster, before and after
   cost per settled answer, before and after accuracy on gold, and the replay that proved
   it. `kourob improvements` prints the node's signed changelog. That changelog is the
   marketing proof, and it can't be faked.
4. **A real student.** Keep nearest-answer as the baseline. Add a trained backend (a
   small embedding model plus a calibrated classifier over settled clusters, or a local SLM
   with LoRA for generative clusters). Promote only when it beats the baseline on gold at
   equal or lower cost. ADR-0009 already made backends pluggable, so this is a new backend,
   not a rewrite.
5. **Prompt/program evolution for T2.** Treat the T2 few-shot prompt as a parameter. Evolve
   it from settled data the way DSPy optimizers do, and gate on gold. That covers the
   clusters that are too varied for rules and too cheap to deserve T3.
6. **Synthetic curriculum.** The teacher paraphrases settled questions to widen T1 and the
   scope classifier's coverage. Calibration stays on gold only, so the student can't learn
   the teacher's paraphrases as truth.
7. **Network-level evolution.** Splits hand the parent's examples to the child. Routes
   already strengthen with use, and the next step is to also weaken them on corrections.
   A desk node learns which neighbour answers which cluster most cheaply. This is where
   "self-improving nodes" becomes "a self-improving network".

## First wedge for real traffic

Pick one. All three are reversible.

- **A. Dogfood on this machine.** Wrap an MCP server that Claude Code sessions here call
  repeatedly (the repo docs node, or a web or doc lookup). Real traffic within days, zero
  outside dependency. Weakest proof, fastest loop.
- **B. The MAUDE/openFDA case study.** The marketing already has it. Repeated structured
  calls against a public API, with reality settlement available because the source revises.
  Strongest story, but it needs the HTTP transport (`kb-imt`).
- **C. An LLM-call cache for agent developers.** Wrap an OpenAI-compatible or Anthropic
  endpoint for one narrow repeated task (classification, extraction). The biggest market
  and the most competition. The shadow teacher plus receipts is the differentiator.

Recommendation: **A now, B next.** A closes the loop on real data this week and exercises
items 1 to 3. B is the public proof once HTTP exists.

## Proposed GOAL.md delta

Keep the sentence. Swap the synthetic-replay metrics for real-traffic ones:

| Metric | Target |
|---|---|
| Labeled fraction of served answers (any settlement source) | ≥ 60 % after 14 days |
| Cost per settled answer, day 30 vs day 1, **on real traffic** | ≥ 5× down |
| Accuracy on gold after every applied change | never below the pre-change value; any regression rolls back automatically |
| Improvements with a signed before/after record | 100 % |
| External callers | ≥ 1 developer replacing a real call |

## Stop or park

- Park new KNP specs, Merkle roots, PROV export, and the pricing ADRs until the loop has
  run on real traffic. They are all correct work, and none of them makes a node learn.
- Park the three-brand marketing sequence. Market KouroB alone, with the improvement ledger
  as the proof.
- Verify the Jev endpoint (`https://api.typesafe.ai/v1/systemone` in
  `runner/adapters/jev.py`) against TypeSafe's live docs before relying on it. The
  2026-09-19 session wrote it and tested it only in scripted mode.
