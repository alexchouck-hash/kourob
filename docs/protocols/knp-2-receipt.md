# KNP-2: Receipts and provenance

Status: draft · Milestone: M1 · Extension URI: `https://kourob.org/ext/receipt/v1`
Depends on: KNP-0

A receipt is the unit of provenance and the unit of metering. It is the only artefact that
crosses node boundaries and is meant to outlive the request.

## 1. What a receipt is and is not

**Is**: a signed statement by one node that it answered one request, at one tier, from
these events, at this cost, after this other receipt.

**Is not**: a copy of the request or the response. Receipts store `sha256:` hashes of both.
A receipt is safe to publish; a request log is not. This is the line that lets the ledger be
shared and the request log stay local under retention (brief §15).

## 2. Wire format

```yaml
id: rcpt_01JBQ7ZK4M8XN2WQ0V7RTYE3PA   # ULID
node: did:key:z6MkShot...
caller: did:key:z6MkAsk... | user:8f3a...
request_hash: sha256:8c9f...
response_hash: sha256:1a02...

scope_result: in_scope | referral | bridge | reject
reason: null | out_of_scope | loop | insufficient_credit | hops_exhausted | policy | unavailable
tier_used: T0 | T1 | T2 | T3 | T4 | null
determinism: derived | attested | adjudicated | declared | null
model_version: rule:agg-014 | student-s@0.4.2 | frontier:<vendor>:<model>

citations: [evt_01J..., evt_01J...]
upstream:  [rcpt_01J...]
hops: [did:key:z6MkAsk..., did:key:z6MkShot...]

cost_credits: 0.0031
price_credits: 0.0050

ts: 2026-09-09T21:04:11Z
prev: sha256:5b7e...          # hash of the previous receipt on this node
sig: <ed25519 over SIGNED_FIELDS, in order>
```

`SIGNED_FIELDS` is an ordered tuple fixed in `src/kourob/ledger/receipt.py`. Changing it is
a breaking change to the ledger format and needs an ADR. Canonicalisation before signing:
JCS (RFC 8785), so two implementations agree byte-for-byte.

### 2.1 Fields the brief did not have, and why

- **`determinism`** — KNP-0 §2. A verifier needs to know whether it can re-run the answer,
  only attest that the node said it, or check it against the node's signed card. Without
  this field every receipt is treated as merely attested, which throws away the main
  benefit of the cost curve.
- **`reason`** — KNP-1 §6. Refusals are the majority of traffic at the edge of a scope, and
  a refusal without a reason is not analysable.
- **`hops`** — KNP-0 §5. Needed to detect and prove cycles after the fact.

## 3. The hash chain

Each node keeps one append-only chain. `prev` is the sha256 of the previous receipt's
canonical form. The genesis receipt has `prev: sha256:` of the node's `did:key`, so a chain
cannot be silently re-parented onto another node's history.

`kourob ledger verify` walks the chain and checks, for every receipt: the signature against
the node's public key, `prev` against the actual predecessor, and monotonic `ts`. It reports
the **first** break, because everything after a break is unverifiable and reporting all of
them is noise.

What this catches: a node operator editing history after the fact. What it does not catch:
a compromised node signing false receipts *going forward*. That needs a transparency log —
Merkle roots published to a set registry (KNP-4 §4), which bounds the damage window to one
publication interval rather than eliminating the risk. Say this out loud rather than
implying tamper-proofing we do not have.

## 4. Provenance graph and PROV export

Receipts plus event provenance stamps form a DAG:

```
answer ──▶ receipt ──▶ events ──▶ sources
              │
              └──▶ upstream receipts ──▶ (another node's events)
```

Exported in W3C PROV vocabulary so external tools can read it without knowing KouroB:

| KouroB | PROV |
|---|---|
| event | `prov:Entity` |
| source | `prov:Entity` |
| receipt | `prov:Activity` |
| node, tool, loop | `prov:Agent` |
| event derived from source | `prov:wasDerivedFrom` |
| answer produced by receipt | `prov:wasGeneratedBy` |
| receipt run by node | `prov:wasAssociatedWith` |
| receipt depends on upstream receipt | `prov:wasInformedBy` |

`kourob trace <receipt_id>` renders this. `kourob ledger export --prov` emits PROV-JSON.

## 5. Inference without an event

KNP-0 I2 says every claim cites an event. Models will produce claims that do not follow
from any event. Three legal responses, in preference order:

1. **Ground it.** Retrieve the events that support the claim, cite them, answer.
2. **Mark it.** Answer with the claim flagged as inference, `citations` covering only the
   grounded parts, and `metadata["…/receipt/v1/ungrounded"]` listing the claim spans.
   `determinism` stays `attested`. A caller may reject ungrounded spans.
3. **Refuse.** `scope_result: reject`, `reason: out_of_scope`.

Silently emitting an ungrounded claim with a confident `citations` list is the single worst
failure this protocol can have, because it launders a guess into the provenance graph and
every downstream node inherits it. The `lint` loop treats an uncited claim on a compiled
page as a build failure for the same reason.

## 6. Outcomes: the edge that makes a node learn

A receipt records what a node *did*. It says nothing about whether the answer was any good.
Without that, the request log is a pile of unlabelled examples and the evolve loop is
guessing — it can make a node cheaper but not better, and cheaper-but-wrong is the failure
mode that kills this design.

So the ledger has one more record type, appended to the same chain: the **outcome**.

```yaml
id: outc_01JBQ8...
node: did:key:z6MkShot...
about: rcpt_01JBQ7ZK4M8XN2WQ0V7RTYE3PA   # the receipt being judged
verdict: accepted | corrected | rejected | superseded | unresolved
source: caller | human | downstream | reality
detail:
  corrected_to: evt_01J...      # for `corrected`: the event that says what was true
  by: did:key:z6MkAsk... | user:8f3a...
  note: "predicted straight sets, match went five"
latency_s: 86400                # how long after the answer the outcome was known
ts: 2026-09-10T21:04:11Z
prev: sha256:...
sig: <ed25519>
```

### 6.1 Where outcomes come from

| `source` | How it arrives | Cost to obtain | Trust |
|---|---|---|---|
| `caller` | The caller POSTs an outcome for a receipt it holds | free | low — self-reported, may be strategic |
| `downstream` | A node that used this answer reports whether its own answer held up | free | medium — the reporter has skin in it |
| `human` | T4 review, or a correction event pushed through the gate | expensive | high |
| `reality` | A later event contradicts or confirms the answer | free, but delayed | **highest** — nobody's opinion |

`reality` is the one worth building for. A prediction node that says *"Alcaraz 0.77"* gets
an unarguable label when the match finishes. A shot-charting node that says *"41-shot
rally"* gets one when a human charts the same point. **Any node whose answers are eventually
settled by an event it will ingest anyway has a free, honest, self-labelling training set,
and it should be designed to notice.**

This is the difference between a node that gets cheaper and a node that gets better. Both
show up in the same ledger.

### 6.2 The outcome window

Every schema declares `outcome_window`: how long after an answer an outcome may still
arrive, and therefore how long a receipt stays *provisional*.

```yaml
# in the ODCS contract
kourob:
  outcome_window: 7d
  outcome_source: reality
  settles_against: match_result.v1   # the schema whose arrival settles it
```

A receipt older than its window with no outcome is `unresolved`, and unresolved is
information: a node whose answers are never settled cannot claim a quality multiplier
(KNP-3 §3) and cannot promote a tier (KNP-5 §3). **Unverifiable work does not get to be
cheap.**

### 6.3 Submitting an outcome

Over A2A, extension `https://kourob.org/ext/outcome/v1`:

```json
{
  "receipt_id": "rcpt_01JBQ7ZK4M8XN2WQ0V7RTYE3PA",
  "verdict": "corrected",
  "detail": { "note": "shot 3 was a backhand, not a forehand" },
  "evidence": ["evt_01JC..."]
}
```

The node validates that the caller is the one named in the receipt's `caller` field,
appends the outcome, and returns its id. An outcome from anyone else is recorded with
`source: caller` and a lower weight, never rejected — a third party noticing an error is
useful even when it cannot be trusted.

### 6.4 Outcomes are not deletions

An outcome never edits or removes a receipt. The wrong answer stays in the chain with a
`corrected` outcome pointing at what was true. This costs storage and buys two things: the
evolve loop can train on the error, and a caller who acted on the wrong answer can prove
what they were told and when.
