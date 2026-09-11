# Status against GOAL.md

Dated 2026-09-10. Rewritten, not appended: this file says where the project *is*, and the
handoffs say how it got there.

## The one sentence

> Any builder can **create a node in one command**, **connect it to other nodes**, and have
> it **become cheaper and better** at its job with every request it serves, while every
> answer it gives can be **traced back to its sources** and its cost can be **metered along
> the whole chain** that produced it.

| Clause | State | What exists | What is missing |
|---|---|---|---|
| create a node in one command | **met** | `kourob init` lays down a working cell that ingests and answers with a citation in seconds | — |
| connect it to other nodes | **met on disk** | `kourob connect`, route table with Hebbian strength, scope check with declared exclusions, referral with route hints, bridge with chained receipts, hop-list refusal, cross-node `trace`; the M3 router eval passes | only the local transport: no A2A card, no HTTP. A remote route is refused rather than guessed at |
| become cheaper | **met, measured** | evolve mines a T0 rule by exact replay; `kourob tend` at A2 installs it as a `node_change.v1` event carrying its inverse, and the node answers from it on the next request; one correction disables it; `kourob rollback` restores the prior state — proven by `tests/test_tend.py` and `evals/promotion_test.py` | v1 mines single-event lookups only; the T1 student is a nearest-settled-answer model, not a trained network; the 30-day replay takes 40 minutes (`kb-0sl`) |
| become better | **met in mechanism** | outcomes, settlement from reality, quality multiplier | only `note.v1` settles; no comparator for probabilistic answers |
| traced back to its sources | **met for one node** | receipts, hash chain, `trace`, tamper detection | upstream receipts across nodes untested because there are no chains yet; no PROV export |
| metered along the whole chain | **met for one node** | measured token cost; price = base × (1 + demand) × earned quality; quotes with a ceiling the receipt never exceeds; free allowance then post-paid debit; `kourob meter report` and `meter price` — proven by `tests/test_metering.py` | credits are internal and no money moves (by design); a bridge does not yet quote both legs; no Merkle roots |

## The six metrics

| # | Metric | Target | Now | Verdict |
|---|---|---|---|---|
| 1 | `init` to a cited answer over MCP | < 10 min | `kourob init`, `kourob attach claude-code`, and an agent lists five tools over stdio and gets a cited, receipted answer — proven by `tests/test_mcp_server.py` against the real server process | **met** |
| 2 | T0+T1 share after 30 days | ≥ 80 % | **measured**: a 30-day, 200/day replay on the tennis cell, starting with T1 off, ends with T0+T1 serving ≥ 80 % — `evals/cost_curve.py` (marked `slow`: one replay takes 40 min, `kb-0sl`) | **met** |
| 3 | cost/request day 30 vs day 1 | ≥ 5× down | the same replay measures it; T0 costs a scan, T1 a JSON lookup, T3 a priced model call, so the ratio is a real number rather than a tier count. Passes at ≥ 5×; the eval asserts the ratio without printing it, which a follow-up should fix | **met** |
| 4 | provenance reconstructible | 100 % | 100 % for one node, proven by tests | **met** (single node) |
| 5 | referral learning | second call goes direct | first call bridges and hands back a route with an evidence receipt; the caller's route table then points at the neighbour; the second call is referred, and a direct call works — proven by `evals/router_test.py` | **met** (local transport) |
| 6 | split proposed within one evolve cycle | yes | yes, with a child manifest, proven by eval | **met** |

Six of six met — 4 for one node, 5 on the local transport, 2 and 3 by a replay that takes
forty minutes and runs only on purpose (`-m slow`).

## Milestones

| | Delivered | Owed |
|---|---|---|
| **M0** | everything | — |
| **M1** | manifest, identity, store, gate (P 1.0 / R 1.0), events, ledger, T0, T3, cascade, MCP handler, init, trace | MCP stdio server; PROV export; schema codegen and diff |
| **M2** | compile loop (pages from events, a citation on every claim, page per key), lint loop (uncited, orphan, hand-edited), `get_page` serving compiled pages, `attach`, the markdown in-port, the dogfood node answering the M2 question from this repo's own docs | packs, the real fresh-agent eval |
| **M3** | scope check with declared exclusions, referral, bridge, routes, connect, hop lists, cross-node trace, router eval — all on the local transport | A2A card and HTTP transport, T1 scope classifier, tennis node |
| **M4** | outcomes, clustering, evolve, split, `tend` with rollback, halts and autonomy demotion, price function, quotes with a ceiling, accounts, allowance refusal, meter report | Merkle roots, ADR-0003/4/5 (owed: KNP-3/4/5 draft the mechanisms) |
| **M5** | rule mining by exact replay, demotion on one correction, the T1 student trained on settled answers and calibrated per class against gold, `kourob distill train|calibrate|gold`, and the 30-day cost-curve replay (slow) | UI, publish; replay performance (`kb-0sl`) |

## Where the design is stronger than the brief

Things learned by building that the brief did not have, all recorded in ADRs or decisions:

- **Outcomes** (ADR-0007). The brief had no source of labels. Now a node can get better, not
  just cheaper, and `source: reality` makes some domains self-labelling.
- **Exact replay** (ADR-0008). A T0 rule is a function or it is gone.
- **Determinism classes** (KNP-0 §2). Cost and trust move together as a node promotes.
- **Cells** (KNP-8). The size ceiling is what stops LLM-built projects exploding.
- **A2A extensions** (ADR-0006). Not a fork.

## Where the code is weaker than the design

Honest list, in the order they bite:

1. **Nodes talk only on disk.** KNP-1, 4 and 9 are now exercised against a second party,
   but over a path, not a wire. The A2A card and HTTP transport are the gap between "works"
   and "works between operators".
2. **Autonomy is exercised only by tests.** `tend` applies, rolls back, halts and demotes,
   and suggests graduation — but no real cell has run at A2 for long enough to say whether
   the ladder's evidence gates are set right.
3. **Serving is slow at scale.** A 30-day replay takes 40 minutes — roughly 400 ms a
   request — so the cost-curve evals are `slow` and off by default. The profile named the
   culprits (`kb-0sl`); the fix is per-request work that is O(receipts) or O(examples).
4. **`answer_entropy` is computed across all history**, so a legitimately updated answer
   reads as non-deterministic and blocks a promotion that should happen.
5. **T3 answers have no `settle_key`**, so the tier most in need of correction is the one
   that never gets settled.
6. **Cluster keys are unreadable** and are about to appear in commit messages.
7. **Keyword retrieval** for T3 will stop scaling, and no measurement says when.
8. **Only MCP has a transport.** A2A and REST are stubs, so nothing outside this machine can
   reach a cell, and `examples/ui` has nothing to talk to.

## The queue

Kept in Beads (`bd ready`), ordered by what moves the sentence, not by milestone number:

1. ~~**Connect**~~ — done on the local transport (`kb-9gv`). What remains of it is the
   A2A card and HTTP (`kb-imt`), which is transport, not mechanism.
2. ~~**Rule mining by exact replay**~~ — done for single-event lookups (`kb-24l`). The
   proposal now carries the rule; `tend` is what installs it.
3. ~~**MCP stdio server**~~ — done (`kb-dj7`). `kourob serve --mcp`, `kourob attach`,
   and metric 1 met on the letter.
4. ~~**`kourob tend`**~~ — done (`kb-2ff`). Decide by autonomy, budget and recorded
   inverse; apply as change events through the gate; halt and demote on breach; rollback.
5. ~~**Price function, quotes, accounts, meter report**~~ — done (`kb-k60`).
6. ~~**Compile and lint, and the dogfood node**~~ — done (`kb-afx`). The repo serves its
   own docs with a citation on every claim.
7. ~~**T1 and the cost-curve eval**~~ — done (`kb-ayo`). Measured over a real 30-day replay; the replay itself is too slow for CI (`kb-0sl`).
8. **Tennis set** — the first real integration.
9. **ADR-0003/4/5, Merkle, PROV export, schema codegen** — owed, not blocking.

Human decisions pending (`bd human`): what settles a probabilistic answer; whether mined
question-matching stays regex; the `kourob.org` namespace; branch protection on a solo
account.
