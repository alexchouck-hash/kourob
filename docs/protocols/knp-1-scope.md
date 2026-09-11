# KNP-1: Scope, refusal, referral, bridge

Status: draft · Milestone: M3 · Extension URI: `https://kourob.org/ext/scope/v1`
Depends on: KNP-0, KNP-2

This is the containment spec. It says how a node declares what it owns, how it refuses
everything else, and how a refusal carries enough information that the caller is better off
than before it asked.

## 1. Why refusal is the interesting part

A node that answers everything is a worse model. A node that refuses cleanly and points
somewhere useful is a router with expertise, and a network of those is cheaper than any
single model, because each request is served by the smallest thing that can serve it.

So the refusal path gets the same care as the answer path: it is typed, it is receipted,
and it carries a route.

## 2. Declaration: the agent card

A KouroB node declares scope in its A2A agent card under the extension:

```json
{
  "name": "tennis-shot-node",
  "version": "0.3.1",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://kourob.org/ext/scope/v1",
        "description": "Declared scope, typed refusals, and referral route hints.",
        "required": false,
        "params": {
          "summary": "Shot-level events for ATP and WTA matches charted since 2011.",
          "schemas":  ["shot.v1", "point.v1"],
          "entities": ["match", "player", "point", "shot"],
          "capabilities": ["query", "aggregate", "chart"],
          "excludes": [
            { "pattern": "betting odds",       "refer_to": "did:key:z6MkOdds..." },
            { "pattern": "match prediction",   "refer_to": "did:key:z6MkPred..." },
            { "pattern": "player biography",   "refer_to": null }
          ],
          "max_hops": 4,
          "determinism": ["derived", "attested"]
        }
      }
    ]
  },
  "signature": "...",
  "signingKey": "did:key:z6MkShot..."
}
```

`excludes` is the load-bearing field and the one most implementations will skip. It is the
node stating, in advance, the things people will wrongly bring to it. A node that has been
running for a month and has an empty `excludes` is not paying attention to its own
quarantine and referral logs.

`refer_to: null` means "not mine, and I don't know whose". That is a legitimate and useful
answer. Guessing would be worse.

## 3. Classification

On each request the node classifies into exactly one of four outcomes:

| `scope_result` | Meaning |
|---|---|
| `in_scope` | Answer it |
| `referral` | Not mine. Here is who, and I am not calling them |
| `bridge` | Not mine. I called them for you this once, here is the answer and the route |
| `reject` | Not mine, and I have no candidate. Or: loop, or budget, or policy |

Classification runs **rules first, model second** (brief §2). The rules are cheap and
explainable; the T1 classifier only sees what the rules could not decide. A node MUST record
which one decided, in the receipt's `model_version` (`rule:<id>` or `student-scope@<v>`),
because the evolve loop mines exactly this to turn model decisions into rules.

## 4. Refusal and referral on the wire

A refusal is a normal KNP-0 envelope. The extension data rides in `metadata`, keyed by the
extension URI:

```json
{
  "data": null,
  "rendered": "Out of scope. This node owns shot-level charting, not match prediction.\nTry did:key:z6MkPred... which reports 0.004 credits and 180 ms for this scope.",
  "citations": [],
  "receipt_id": "rcpt_01JBQ7...",
  "metadata": {
    "https://kourob.org/ext/scope/v1/scope_result": "referral",
    "https://kourob.org/ext/scope/v1/matched_exclude": "match prediction",
    "https://kourob.org/ext/scope/v1/decided_by": "rule:excl-002",
    "https://kourob.org/ext/scope/v1/route_hints": [
      {
        "node": "did:key:z6MkPred...",
        "scope": "match prediction",
        "endpoint": "https://predict.example/a2a",
        "cost_credits": 0.004,
        "latency_ms": 180,
        "last_success": "2026-09-09T18:22:04Z",
        "evidence": "rcpt_01JBQ2..."
      }
    ]
  }
}
```

`evidence` is the receipt of the last time this node actually observed that route working.
A route hint with no evidence is hearsay, and a caller is entitled to weight it lower. This
is the whole defence against route poisoning at the v1 trust level: a lying node can claim
anything, but it cannot produce a receipt signed by a node that never answered.

## 5. Bridging

A bridge is a referral the node executes on the caller's behalf, once.

```
caller ──▶ A  (out of scope, knows B)
             A ──▶ B ──▶ answer + rcpt_B
       ◀── answer + rcpt_A(upstream: [rcpt_B]) + route_hint{B}
```

The response is an `in_scope`-shaped envelope with `scope_result: bridge`. `citations` are
**B's** event ids, not A's — A has no events for this and must not pretend otherwise. The
receipt chain is what ties them: `rcpt_A.upstream = [rcpt_B]`, and `kourob trace` walks it.

### 5.1 The bridge budget

A node bridges a given `(caller, scope_pattern)` pair at most `bridge_limit` times
(default 3), then refers only. The counter is per pair, persisted, and visible to the
caller:

```json
"https://kourob.org/ext/scope/v1/bridge": {
  "used": 2,
  "limit": 3,
  "resets": null
}
```

`resets: null` means never — the budget is a one-time courtesy, not a rate limit. The point
is not to ration; it is to make the network converge. A caller that keeps coming back to A
for B's work is paying A's margin on top of B's price for no reason, and after three hops
A stops letting it.

### 5.2 Why bridge at all

Bridging is strictly worse than a direct call for everyone involved: A pays B, A adds
latency, A adds margin. It exists for exactly one reason — **the caller does not yet know B
exists.** The bridge is a paid introduction, and `bridge_limit` is how long the introduction
lasts.

This is the mechanism by which the network finds short paths without a global optimiser.
Nobody computes the shortest route. Every caller learns one hop at a time from receipts it
already paid for.

### 5.3 When a node MUST NOT bridge

- The hop list already contains the target (KNP-0 §5).
- The caller's credit balance cannot cover A's price *plus* B's quoted price. A quotes both
  separately (KNP-3 §4) and refuses rather than running up a debt on the caller's behalf.
- `bridge.enabled` is false in the manifest, or the target's card does not currently verify.
- The target is outside A's set and A's trust policy is `set-only` (KNP-4 §5).

## 6. Refusal reasons

`reject` carries a machine-readable reason so the evolve loop can count them:

| `reason` | Meaning | What evolve does with it |
|---|---|---|
| `out_of_scope` | No candidate node known | Counts toward an `excludes` proposal, or a new-node proposal if the cluster is large |
| `loop` | Hop list contained this node | Flags the route that produced the cycle |
| `insufficient_credit` | Caller cannot pay the quote | Nothing; this is the meter working |
| `hops_exhausted` | `max_hops` reached | Flags a chain that is too long — usually a missing direct route |
| `policy` | Blocked by a node policy (PII, consent, minors) | Escalates to the human. Never auto-resolved |
| `unavailable` | Upstream needed and unreachable | Decays that route's score in the route table |

A node MUST NOT collapse these into a single "no". The distinction between "not mine" and
"mine but I can't right now" is the difference between the caller re-routing and the caller
retrying, and getting it wrong wastes the network's money.

## 6.1 Transports

The mechanism above is transport-independent, and the first transport is a **path**:
`kourob connect ./sibling-cell` writes a route whose endpoint is a directory, and a bridge
opens that directory and asks it over the same `serve.answer` a remote caller would reach
over the wire. Even locally, nothing crosses by import: the neighbour writes its own receipt
in its own ledger, signed with its own key, and `kourob trace` follows the `upstream` id
into that ledger.

This is deliberate ordering, not a shortcut. The whole loop — scope check, referral,
bridge, chained receipts, route learning, hop refusal — was untested against a second party
until it could be tested with two directories and no server. HTTP over A2A attaches behind
the same `Neighbour` contract (`ports/local.py`) and changes nothing above it. Until it
lands, a route whose endpoint is a URL is **refused, not guessed at**: the failure mode of
guessing a transport is a request that goes nowhere and a receipt that says it went
somewhere.

## 7. Scope drift

A node's declared scope and its served scope diverge over time. Two named failure modes,
both detected by the `lint` loop against the request log:

- **Overclaim**: scope declares a schema the node has no events for and has refused every
  request against for `drift_window`. Fix: shrink the declaration. Overclaim is worse than
  underclaim because it poisons other nodes' route tables.
- **Underclaim**: the node is answering a cluster well that its declaration does not cover
  — usually because the T3 tier is quietly generalising. Fix: either declare it, or stop
  answering it. Answering outside the declaration is a violation of I3 even when the answer
  is good.

Both produce an `evolve` proposal, not an automatic change. Scope is the node's contract
with everyone who routed to it, and it does not get edited without a human.
