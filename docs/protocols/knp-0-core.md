# KNP-0: Core

Status: draft · Milestone: M1 · Depends on: nothing

The invariants every other KNP spec assumes. If an implementation breaks one of these, the
rest of the suite stops meaning anything.

## 1. The three invariants

### I1. Every response is an envelope

Every port handler, on every path — success, refusal, referral, error — returns:

```json
{
  "data":       <structured result, typed by the schema it came from, or null>,
  "rendered":   "<markdown view of the same result>",
  "citations":  ["evt_...", "evt_..."],
  "receipt_id": "rcpt_..."
}
```

`citations` MAY be empty **only** when `scope_result` is `referral` or `reject`. Everywhere
else an empty `citations` is a protocol violation, because it means the node produced a
claim it cannot source.

`receipt_id` is never empty. A node that cannot write a receipt MUST fail the request
rather than answer without one. This is the single rule that makes the whole network
auditable, and it is the one most tempting to relax under load.

### I2. Every claim cites an event

A citation is an event id in this node's store, or a receipt id from an upstream node
(which in turn cites events). The chain terminates at events, and events carry provenance
stamps naming their source. There is no third kind of ground truth.

Consequence: a node cannot answer from its model's parametric memory. If T1 or T3 produces
a claim with no supporting event, the cascade MUST either find supporting events, lower
the claim to an explicitly-marked inference, or refuse. See KNP-2 §4.

### I3. Scope is closed

A node answers what it declares and refuses everything else. "Refuses" is a first-class,
receipted outcome, not an error. See KNP-1.

Consequence: a node's competence is bounded and **stated**, so a caller can reason about
where to go next without trying. This is what makes a network of nodes cheaper than one
large model: the routing is declared, not learned per request.

## 2. Determinism classes

Every answer carries a determinism class, because it changes what a third party can do with
the receipt.

| Class | Meaning | What a verifier can do |
|---|---|---|
| `derived` | T0: a rule or SQL view over silver events | **Re-run it.** Given the same events, any party computes the same answer and checks the response hash themselves |
| `attested` | T1–T3: a model produced it | **Attest only.** The receipt proves *this node said this*, at this time, from these events, at this model version. It does not prove the answer follows |
| `adjudicated` | T4: a human accepted it | Attest, plus the reviewer identity is in the receipt |

The brief's tier ladder is a cost ordering. This is a *trust* ordering, and it does not map
one-to-one onto cost: a cheap T0 answer is more verifiable than an expensive T3 one. Both
belong in the receipt.

This distinction is why the cost curve is not merely a saving. As a node promotes work down
the tiers (KNP-5), a growing fraction of its answers move from `attested` to `derived` —
that is, from "trust this node" to "check it yourself". **The node gets cheaper and more
trustworthy along the same axis.**

## 3. Identity

A node is identified by `did:key:z6Mk...` over an ed25519 public key. No registry is
required to verify a signature, which is what lets two nodes interact before they share a
set.

A caller is identified by a node `did:key` or by `user:<opaque-id>`. A node MUST NOT put a
human-readable user identifier in a receipt; receipts are long-lived and may be published.

## 4. Versioning

- **Protocol version** rides in the A2A extension URI: `.../ext/scope/v1`. A breaking
  change mints `/v2`. Both may be served during a transition.
- **Schema version** is the ODCS contract id, e.g. `shot.v1`. Schema versioning is
  independent of protocol versioning.
- **Model version** is a string in the receipt: `student-s@0.4.2`, `frontier:<vendor>:<model>`,
  or `rule:<id>`. It is opaque to the protocol and meaningful to the node.

A node MUST reject a request that activates an extension URI it does not serve, rather than
silently ignoring it. Silence here is how provenance guarantees rot.

## 5. Hop list and loop prevention

Every inter-node request carries a hop list: the ordered `did:key`s of nodes already
involved. A node MUST refuse a request whose hop list already contains its own id, and MUST
append its id before calling onward. `max_hops` in the manifest bounds the total.

A refusal for this reason is `scope_result: reject` with `reason: "loop"`, and it is
receipted like any other, so a routing cycle shows up in the ledger rather than as a
timeout.

## 6. Errors

There is no separate error shape. A failure is an envelope with `data: null`, a `rendered`
explanation, and a receipt whose `scope_result` is `reject`. The reason is machine-readable
in the receipt.

This is deliberately inconvenient: it means a node cannot fail cheaply and silently. Every
failure costs a receipt write, and every failure is therefore visible to the evolve loop,
which is exactly where failures should be visible.
