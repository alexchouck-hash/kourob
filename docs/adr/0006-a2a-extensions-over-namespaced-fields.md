# ADR-0006: Carry KouroB semantics as A2A extensions, not a `kourob.*` namespace
Status: accepted
Date: 2026-09-10

Context:
  Brief section 9 says the agent card is "extended with KouroB scope, price, and Merkle
  root" and that "extension fields are namespaced `kourob.*`". That was written against a
  pre-1.0 A2A. A2A has since released 1.0.0 with a first-class extension mechanism
  (spike: docs/spikes/2026-09-10-a2a-extension-mechanism.md).

  The choice matters more than it looks. It decides whether a KouroB node is an A2A agent
  that carries extra semantics, or a dialect of A2A that only KouroB clients can talk to.

Options considered:
  A. **Namespaced fields on the card, as the brief describes.** Add `kourob.scope`,
     `kourob.price`, `kourob.ledger_root` as top-level card keys. Simple, and works today.
     Rejected: it is a fork by accretion. A2A validators reject unknown top-level fields or
     silently drop them, there is no negotiation so a client cannot say what it understands,
     and there is no versioning path short of renaming the keys.
  B. **A2A extensions.** Declare extension URIs in `capabilities.extensions[]`, negotiate
     with the `A2A-Extensions` header, carry data in `metadata` keyed by the extension URI.
     Versioned in the URI. Spike confirms the mechanism, the header, and the metadata
     convention.
  C. **A separate KouroB endpoint alongside A2A.** A parallel `/kourob/v1` API carrying the
     extra semantics. Not explored with a spike because it doubles the surface area, splits
     the security model, and gives up the reason for using A2A at all — a caller would have
     to know KouroB before it could discover a KouroB node.
  D. **Push it all into A2A `skills`.** Model scope as skills and price as skill metadata.
     Not explored with a spike because `skills` describes what an agent can do, not what it
     refuses, and refusal is the load-bearing half of KNP-1.

Decision:
  Define five extension URIs, one per KNP spec:

    https://kourob.org/ext/scope/v1      KNP-1  scope, refusal, referral, bridge
    https://kourob.org/ext/receipt/v1    KNP-2  receipts and provenance
    https://kourob.org/ext/meter/v1      KNP-3  quotes and credits
    https://kourob.org/ext/registry/v1   KNP-4  sets, routes, trust
    https://kourob.org/ext/outcome/v1    KNP-5  outcome submission

  All are declared `required: false`. Extension data rides in `metadata` under the URI, per
  the A2A convention. Use A2A's own agent card signing (`signature` / `signingKey`) with the
  node's `did:key` rather than a parallel signing scheme.

Consequences:
  - A plain A2A client can call a KouroB node and get a usable answer. It gets no receipt
    id it can act on, no route hint, and no quote — which is the honest trade, and it means
    adoption does not require the whole stack.
  - A node MUST reject a request activating an extension URI it does not serve
    (KNP-0 section 4). Silently ignoring an activation is how provenance guarantees rot.
  - `required: false` everywhere means a caller can always opt out of metering. Metering
    is therefore enforced by the node refusing to *answer* without a receipt, not by the
    extension being mandatory.
  - The URIs are a public commitment. Register them under w3id.org before anyone
    implements against them, or accept that they will rot.
  - Brief section 9's `kourob.*` wording is superseded by this ADR.

Revisit when:
  A2A ships a breaking change to the extension mechanism, or a second transport (gRPC,
  JSON-RPC) is needed and the metadata convention does not carry cleanly across it.
