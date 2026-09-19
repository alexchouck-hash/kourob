# 2026-09-10 · claude-code · protocols, evolution, and integration

Task: brainstorm the connect-and-evolve mechanism, write the protocols down, find what
existing work can be integrated, and continue development.

## Done

### Protocols — `docs/protocols/`, six specs

KNP-0 core (three invariants, determinism classes, hop lists, errors) · KNP-1 scope,
refusal, referral, bridge · KNP-2 receipts, provenance, **outcomes** · KNP-3 quotes and
credits · KNP-4 sets, registries, routes, trust · KNP-5 promotion, demotion, shedding,
split, cross-node distillation.

Two structural findings changed the design:

1. **A2A shipped 1.0 with a real extension mechanism.** The brief's `kourob.*` namespaced
   fields are superseded — see the spike and ADR-0006. Five extension URIs, negotiated with
   the `A2A-Extensions` header, data in `metadata` keyed by URI. A plain A2A client can
   still call a KouroB node and get a usable answer.
2. **The brief has no source of labels.** Section 6.3 says a T3 pull "becomes a labeled
   example for T1" but never says where the label comes from. Without one the evolve loop
   can make a node cheaper but not better. Fixed by adding **outcomes** to the ledger
   (ADR-0007) and changing the objective to cost per *settled* request.

### Decisions — three new ADRs

- **0006** A2A extensions over a `kourob.*` namespace, with a supporting spike.
- **0007** Outcomes as a ledger record; objective is cost per settled request.
- **0008** A T0 rule promotes only on **exact** replay over every settled request in its
  cluster. One `corrected` outcome demotes it with no grace period.

### Integration — `docs/integration/tennis-set.md`

Three of your repos already implement most of this by hand, independently:

- `tennis-live-stream-analysis` — `ShotEvent` with
  `EventSource = heuristic | bilstm | audio_pose` plus `confidence` is a tier cascade with
  confidence bars. `data/labels/*.csv` is a gold set.
- `tennis-predict` — "Deterministic, reproduces exactly on rebuild" is the `derived`
  class; "67.1% accuracy, 0.2079 Brier, tail ECE 0.0128" is the gold eval that gates T1;
  `artifacts/champion.json` + `conf_bins.json` is a model registry with calibrated
  thresholds; `AGENT_QUEUE.md` is Beads; the GRAVEYARD is `docs/experiments/`.
- `tennis-predict-site` — `llms.txt` is an agent card in prose; `track_record.json` is a
  settled-outcome log.

**The clearest single payoff:** `llms.txt` claims *"Timestamps prove predictions precede
matches."* Today they do not — a static JSON file can be rewritten. A hash-chained signed
receipt ledger makes that sentence true. That is `kb-id9`, and it is a day of work, not a
milestone.

Tennis is also the best first domain for a reason that generalises: **a match finishing is
a free, honest, unarguable label** (`source: reality`). Domains where answers are settled by
data the node ingests anyway are strictly better node candidates.

### Code

`src/kourob/protocols.py` (extension URIs, one place) · `types.py` gains `Determinism`,
`RefusalReason`, `TIER_DETERMINISM`, `Answer.metadata`, `Answer.is_grounded()` ·
`ledger/receipt.py` gains `determinism`, `reason`, `hops` in `SIGNED_FIELDS` ·
`ledger/outcome.py` new · `loops/evolve.py` gains the real models
(`ClusterStats`, `Proposal`, `EvolveReport`, `Objective`).

18 new contract tests, including doc-code drift checks in both directions on the extension
URIs. `evals/promotion_test.py` covers the two claims KNP-5 §10 admits are untested.
**48 passed, 21 xfailed.**

### Tasks

11 new Beads tasks with dependencies, including the three ADRs the brief owes (0003, 0004,
0005) and `kb-be8`, `kourob.testing`, which every eval already references and nothing
provides.

## Not done

- **No M1 implementation.** The session went to design and contracts, which is what was
  asked. `bd ready` still leads with the M1 store, manifest, runner, and schema tasks.
- **ADR-0003, 0004, 0005 still not written.** KNP-3, 4 and 5 draft their mechanisms; the
  ADRs owe the rejected options. Tasks exist.
- **`kourob.org` is not registered.** The extension URIs assume it.

## Surprises

1. **A2A 1.0's extension mechanism is better than what the brief specifies**, and it has
   agent-card signing built in, so our ed25519 `did:key` becomes the `signingKey` instead
   of a parallel scheme.
2. **`tennis-predict` independently converged on the same conventions** — immutable
   evidence archive vs living docs, a graveyard of negative results with the numbers that
   killed them, an agent queue. That is the strongest evidence available that this design
   describes something real, and it means the integration is mostly renaming.
3. **`tennis-predict` is 750 MB**, nearly all `artifacts/`. It will be the first real test of
   the prune loop and scope shedding, and the first evolve run will propose shedding more
   than is comfortable.
4. **Git Bash here truncates commands at ~8 KB**, which shows up as `unexpected EOF while
   looking for matching quote`. Split long heredocs.

## Open questions

1. **`kourob.org`** — register it, use `w3id.org`, or pick another namespace? Blocking only
   when someone else implements against the URIs.
2. **Cost per settled request may make the 5x target unreachable** in domains that settle
   slowly. If so, report both numbers rather than widening the denominator. Worth deciding
   before M5 rather than during it.
3. **Is `tennis-predict` the node, or is the node a new thing that calls it?** The
   integration doc assumes wrap-not-port, but the determinism claim ("reproduces exactly")
   only becomes third-party checkable if the feature pipeline reads solely from silver. That
   may be the largest piece of work in the whole integration and it deserves its own spike.
4. **Branch protection blocks you from merging your own PRs** (enforce_admins + 1 review,
   solo account). Still unresolved from the last session.

## Resume

```bash
cd C:/Users/houck/kourob
git checkout feat/protocols-and-evolution
uv run pytest -q          # 48 passed, 21 xfailed
bd ready
```

Reading order for a reviewer: `docs/protocols/knp-0-core.md`, then KNP-2 §6 (outcomes),
then ADR-0007 and ADR-0008, then `docs/integration/tennis-set.md`.

Next, in dependency order: `bd show kb-b0r` (store) unblocks most of M1; `bd show kb-p4q`
(outcomes) unblocks all of M4 and M5.
