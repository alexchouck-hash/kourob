# 2026-09-10 · claude-code · demand clustering and the evolve loop

Task: `kb-dvm`. Closed. `kb-be8` (testing fixtures) partly done.

## Done

### The request log — `src/kourob/request_log.py`

The dataset the node evolves against, and it did not exist: the `requests` table was
declared and nothing wrote it. Every request now lands there, whatever happened to it.

Separate from the ledger on purpose: a receipt is **published** and stores hashes; a request
row is **local**, subject to retention, and stores the question — because you cannot cluster
demand you cannot read.

### Clustering — `src/kourob/loops/clustering.py`

Cluster key = the **decision path** for an answered request (rule or tier, schemas, tools,
answer shape) and the **question frame** for a refused one, because a refusal has no
decision path and refusals are where declared scope and real demand disagree.

The frame is the part of a question that survives changing its subject: "what is a bridge"
and "what is a cell" share one. **I got this backwards first** — kept the subject, dropped
the frame — which looks like clustering and is not: every topic becomes its own cluster.

Stats per cluster: volume, tier mix, cost per settled, settle rate, accept rate, event
fanout, and `answer_entropy` — distinct answers per distinct (question, event-set), where
1.0 means the cluster has always been a function, and functions belong in T0.

### The evolve loop — `src/kourob/loops/evolve.py`

Reads the request log, ledger and quarantine; emits an objective, clusters, proposals and
**declines**. Never a change.

| Proposal | Gate |
|---|---|
| promote | settled examples per rung; T0 additionally needs `answer_entropy == 1.0` |
| shed | a declared schema nothing reads, nothing writes, and nothing settles against |
| split | demand factor over threshold **and** two clusters over min share on disjoint schemas |
| rule_from_quarantine | one gate step repeated 20 or more times |
| scope_drift | a refusal cluster over 25 requests |

Every failed gate becomes a `DeclinedProposal` with its reason and a `windows_declined`
count carried from prior reports, so the next window re-evaluates against fresh volume
rather than re-deriving from nothing.

`kourob loop run evolve` and `kourob loop list` are wired. Reports persist to
`logs/evolve/*.json`.

### Verified end to end

- bimodal demand over capacity → **split**, with a real child manifest, a narrowed parent
  scope and a referral rule;
- noisy unimodal demand over capacity → **no split**, declined as "a scaling problem, not a
  splitting problem";
- an unsettled cluster → **no promotion**, declined as "unverifiable work does not get to be
  cheap".

Three previously-xfail evals now pass for real. **129 passed, 12 xfailed.**

## Surprises

1. **The Store silently dropped columns.** `pa.Table.from_pylist` infers its schema from the
   *first* record, so a batch of receipts followed by outcomes wrote the receipt columns and
   dropped every outcome field — leaving signatures over data that was no longer there. A
   data-loss bug, silent, found only because a synthetic fixture wrote a mixed batch. Rows
   are padded to the union of keys now, and `tests/test_store.py` holds the regression.
2. **The loop proposed shedding the schema that settles everything else.** A shed rule that
   counts only reads will eventually delete a node's ability to improve. A schema now earns
   its place three ways, and only the first is obvious.
3. **`append` is quadratic in a batch** because it re-reads the chain per record. Added
   `Ledger.extend`. Found by a fixture that hung, not by reading.
4. **"us" was a frame word.** It collided with the country in "who wins the us open" and
   split one cluster into two. A frame word that is also a subject is worse than a missing
   frame word.

## Not done

- **`kourob tend`** — the loop produces proposals; nothing applies them. That is KNP-7 and
  needs the autonomy ladder plus recorded inverses.
- **Rule mining** (`kb-24l`) — the loop *proposes* T1 to T0; it does not mine or replay the
  candidate. That is ADR-0008's exact-replay gate and the next real piece.
- **The other five loops** — `loop list` says which are stubs rather than pretending.
- **Payback estimates.** `Proposal.pays_back` exists; nothing computes `payback_requests`,
  so no proposal is currently declined on cost.

## Open questions

1. **Cluster keys are long and ugly** (`rule:note-lookup|note.v1|-|{body,id,source,topic}`).
   Fine for machines, poor in a PR a human reads. Worth a stable short id before `tend`
   starts putting them in commit messages.
2. **`answer_entropy` over a moving event set.** Adding an event legitimately changes an
   answer, which reads as entropy above 1.0 and would block a promotion that should happen.
   The metric needs computing per event-set version, not across all history. Not a problem
   at these volumes; it will be.
3. Everything still open from the previous handoffs.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest -q
D=/tmp/demo && uv run kourob init $D && uv run kourob ingest $D/fixtures/events.jsonl --node $D
uv run kourob query "what is a bridge" --node $D
uv run kourob loop run evolve --node $D
bd ready
```

Next: `bd show kb-24l` — rule mining by exact replay, which is what turns a promotion
proposal into a cost curve.
