# The tennis set: three existing repos, one node network

Three repositories in `alexchouck-hash` already implement, by hand and independently,
most of what KouroB specifies. They are the obvious first set — not because tennis is
special, but because they were built without reference to this design and still converged
on it, which is the strongest available evidence that the design describes something real.

## 1. What is already there

### `tennis-live-stream-analysis` — an ingest node in all but name

`tennis_analysis/schema.py` defines `ShotEvent` with `shot_id`, `t_contact`, `shot_type`,
`spin`, `taken_from` / `shot_location` as court coordinates, `footwork`, `outcome`,
`point_id`, `rally_len` — and, critically:

```python
EventSource = Literal["heuristic", "bilstm", "audio_pose"]
confidence: float
event_confidence: float | None
```

That is **a tier cascade with confidence bars**, written before this brief existed.
`heuristic` is T0, `bilstm` is T1, `audio_pose` is a T1/T2 fusion. The node already records
which tier produced each event and how sure it was — the two fields the receipt needs.

`data/labels/*.csv` (`rg2026_3400_exhaustive.csv`, `wimbledon2019_25m_events.csv`, …) are
**gold sets**: human-charted ground truth, already held separate from the pipeline.

### `tennis-predict` — a node with tiers, calibration, and a graveyard

The README states the two things this project spends five milestones trying to guarantee:

> *"Deterministic — the build reproduces exactly on rebuild."* → the `derived` determinism
> class (KNP-0 §2), asserted for the whole pipeline.
>
> *"Current holdout (2025–26): 67.1% accuracy, 0.2079 Brier, tail ECE 0.0128."* → a gold
> set, a calibration measurement, and a per-class error metric. This is what KNP-5 §3.2
> requires before T1 may be enabled, and it already exists.

`artifacts/` carries `champion.json`, `conf_bins.json` (confidence bins — a calibrated
cascade bar), `model_bakeoff.json`, and dated `_prechampion_backup_*` directories. That is
a model registry with versioned promotion, which is `tiers/t1/` plus KNP-5's promotion
record.

The conventions match too: `AGENT_QUEUE.md` is Beads; "six living docs that must stay
current and a write-once evidence archive that must not be edited" is exactly the
pages-are-compiled / events-are-immutable split; the GRAVEYARD of negative results "with the
numbers that killed them" is `docs/experiments/`.

### `tennis-predict-site` — an out-port and a proto agent card

`llms.txt` declares scope, machine-readable endpoints, refresh cadence, and a contact for
richer data. That is an agent card written in prose. `predictions.json` carries
`confidence` and `confidence_band` per row. `track_record.json` is a settled-outcome log.

And this line, from `llms.txt`:

> *"Timestamps prove predictions precede matches."*

They do not, today. A static JSON file's timestamps prove nothing to a sceptic; the file
can be rewritten. **A hash-chained, signed receipt ledger (KNP-2 §3) makes that sentence
true** — the claim the site already wants to make is the exact guarantee KouroB was built
to provide. This is the clearest single payoff in the whole integration.

## 2. The mapping

| Existing | KouroB | Spec |
|---|---|---|
| `ShotEvent` dataclass | `shot.v1` ODCS contract | brief §9 |
| `EventSource` heuristic/bilstm/audio_pose | `tier_used` T0/T1/T2 | KNP-0 §2 |
| `confidence`, `event_confidence` | cascade confidence bars | KNP-5 §3 |
| `data/labels/*.csv` | `data/gold/` | brief §8 |
| pipeline output | `kourob ingest` through the gate | KNP-0 |
| `artifacts/champion.json` | `tiers/t1/` + promotion record | KNP-5 §3.2 |
| `artifacts/conf_bins.json` | calibrated cascade thresholds | KNP-5 §3.2 |
| holdout accuracy / Brier / ECE | gold eval gating T1 | KNP-5 §3.2 |
| `AGENT_QUEUE.md` | Beads (`bd`) | brief §9 |
| GRAVEYARD | `docs/experiments/` | AGENTS.md §2 |
| `llms.txt` | A2A agent card + `ext/scope/v1` | KNP-1 §2 |
| `predictions.json` | REST out-port `data` | KNP-0 I1 |
| `track_record.json` | settled outcomes | KNP-2 §6 |
| match result settles a prediction | `source: reality` outcome | KNP-2 §6.1 |
| Grok traits via `XAI_API_KEY` | a `runner/` adapter | AGENTS.md §4 |

## 3. The set

Three nodes, one set, connected by the protocols rather than by imports:

```
  broadcast video ──▶ [ chart-node ]  shot.v1, point.v1
                          │  derived from audio-onset + pose, gold-labelled
                          │
                          ▼  A2A + ext/receipt/v1
                      [ predict-node ]  match_prediction.v1
                          │  Elo/form features, XGB+LGBM ensemble, closed-form point engine
                          │
                          ▼  REST out-port
                      [ site ]  a thin client, no node-specific code
                          │
  match result ─────────────▶ outcome{source: reality} back to predict-node
```

**chart-node** (from `tennis-live-stream-analysis`). Owns `shot.v1` and `point.v1`. Its
tiers already exist as `heuristic` / `bilstm` / `audio_pose`. Its gold is `data/labels/`.
Scope excludes prediction and refers to predict-node.

**predict-node** (from `tennis-predict`). Owns `match_prediction.v1` and the derivative
prices. Consumes `shot.v1` from chart-node when charted data is available and falls back to
its results backbone when it is not — a bridge with a real cost difference, which makes it
a genuine test of KNP-1 §5 rather than a demo.

**site** (from `tennis-predict-site`). A caller, not a node. It renders `data` and
`rendered` from predict-node's REST port, plus a receipt id per row.

The settlement loop is what makes this set worth building first: **a match finishing is a
`source: reality` outcome** (KNP-2 §6.1). Predict-node's answers are labelled, for free,
by an event it was going to ingest anyway. It has the honest self-labelling training set
that KNP-5 §1 requires, and almost no other domain hands you one.

## 4. Order of work

1. **M3 — chart-node.** Wrap, do not port. `shot.v1` is generated from `ShotEvent`;
   `tennis_analysis.pipeline` becomes an ingest source that pushes through the gate;
   `data/labels/*.csv` moves to `data/gold/`. Nothing in the vision pipeline changes.
   This is also the referral target in `evals/router_test.py`.
2. **M4 — predict-node, receipts first.** Before any tier work: put every published
   prediction through a receipt. This alone makes the `llms.txt` timestamp claim true, and
   it is a day of work, not a milestone.
3. **M4 — outcomes.** Wire match results as `source: reality` outcomes against prediction
   receipts. `track_record.json` becomes a *view* over settled receipts rather than a
   separate file that has to be kept honest by hand.
4. **M5 — promotion and the cost curve.** With real settled outcomes, run KNP-5 for real.
   `evals/cost_curve.py` stops being synthetic.
5. **M5 — the site as reference UI.** If it can render predict-node with no
   tennis-specific code, `examples/ui` is done and the constraint in brief §12 M5 is met by
   something that already has users.

## 5. What this will cost, honestly

- **`tennis-predict` is 750 MB**, most of it `artifacts/`. Under brief §5.3 that is exactly
  what the `prune` loop and KNP-5 §6 shedding exist for, and it will be the first real test
  of both. Expect the first `evolve` run against it to propose shedding more than is
  comfortable.
- **Determinism is claimed, not yet proven to a third party.** "Reproduces exactly on
  rebuild" is a property of the build; `derived` in KNP-0 §2 is a property a *stranger* can
  check from the events. Closing that gap means the feature pipeline reads only from silver.
  That may be the largest single piece of work in the whole integration.
- **`XAI_API_KEY` for Grok traits** is a model call outside `runner/`. It must move behind
  an adapter before predict-node can meter itself, because an unlogged call is an unmetered
  cost (AGENTS.md §4).
- **Coupling risk.** Three repos that currently ship independently become a set with a
  shared trust root. If chart-node's schema breaks, predict-node's tiers invalidate
  (KNP-5 §5). That is correct behaviour and it will be annoying the first time.

## 6. Beyond tennis

`Sinus_CFD` (CT-based airflow and drainage) is the useful second set precisely because it
shares nothing with tennis: different schemas, different tools, different operator context.
A cross-domain referral between two sets that share no vocabulary is the real test of
KNP-4 §5 trust levels, and it is a better test than a second tennis node would be.

The `10X_Gap_Scan` / `10X-Pulse-Maker` / `10x-medtech` repos look like a third set — a
scanning node, a generation node, and a site — but they are private and moving, and a set
should be built from something that has stopped changing shape.
