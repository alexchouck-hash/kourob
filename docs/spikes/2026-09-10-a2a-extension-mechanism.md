# Spike: does A2A have a real extension mechanism, or do we bolt fields on?

Date: 2026-09-10 · Time box: 1 session · Informs: ADR-0006

## Question

Brief section 9 says the agent card is *"extended with KouroB scope, price, and Merkle
root"* and that *"extension fields are namespaced `kourob.*`"*. That was written before
A2A 1.0. Does A2A now define an extension mechanism we should use instead of inventing a
namespace?

## What was found

A2A released **1.0.0**. It has a first-class extension mechanism, and it is better than
the namespaced-field approach the brief assumed.

**Declaration.** Extensions are declared inside `capabilities.extensions[]` on the agent
card, as objects, not as loose keys:

```json
"capabilities": {
  "extensions": [
    {
      "uri": "https://example.com/ext/konami-code/v1",
      "description": "Provide cheat codes to unlock new fortunes",
      "required": false,
      "params": { "hints": [] }
    }
  ]
}
```

**Activation.** The client sends `A2A-Extensions: <comma-separated URIs>`. The server
echoes back the same header listing what it actually activated. So activation is
negotiated per request, not assumed.

**Required.** `required: true` means a client must comply or be rejected. The A2A guidance
is explicit that *data-only* extensions should not be marked required.

**Carrying data.** Extension data rides in existing `metadata` maps under a key that is the
extension URI plus a path, e.g. `"https://example.com/ext/konami-code/v1/code": "..."`.
Core structures are not modified.

**URI convention.** Official extensions use
`https://a2a-protocol.org/extensions/{name}/v{n}`; third parties are advised to version
the URI and to use a permanent identifier service (w3id.org) so the URI does not rot.

**Adjacent findings, relevant to us:**

- A2A 1.0 has **agent card signing** built in: `signature` and `signingKey` fields with a
  defined canonicalisation. We were going to sign cards ourselves with the node's ed25519
  key. We should use theirs instead.
- Transports: JSON-RPC, gRPC, and HTTP+JSON/REST. Clients send an `A2A-Version` header.
- `capabilities.extendedAgentCard` plus `GetExtendedAgentCard` returns a fuller card to an
  authenticated caller. That is exactly the surface for price and balance, which we do not
  want to publish to anonymous callers.
- Task states include `REJECTED` and `AUTH_REQUIRED`. A scope refusal maps to `REJECTED`
  without inventing a state.

## What it means

1. **Do not invent a `kourob.*` namespace.** Declare four extension URIs and carry data in
   `metadata` under them. This is the difference between being an A2A agent that happens to
   be a KouroB node and being a fork of A2A.
2. **A node that speaks no KouroB extension is still callable.** Extensions are negotiated,
   so a plain A2A client gets a plain answer. Containment does not require the caller to
   opt in — but provenance and metering do, which is the honest trade.
3. **Mark the scope extension `required: false`.** It is data-only. A caller that ignores
   it still gets a refusal, just without the machine-readable route hint.
4. **Use A2A card signing** rather than a parallel scheme. Our `did:key` becomes the
   `signingKey`.

## Not explored

- gRPC and JSON-RPC bindings. v1 serves HTTP+JSON only; the extension mechanism is
  transport-independent, so this does not change the design.
- `w3id.org` registration for the extension URIs. Worth doing before anyone else
  implements against them; not blocking, since the URIs are opaque identifiers.

## Sources

- https://a2a-protocol.org/latest/specification/
- https://a2a-protocol.org/latest/topics/extensions/
