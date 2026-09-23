# ADR-0010: A model-tier answer takes its settle_key from its citations
Status: accepted
Date: 2026-09-22

Context:
  `settle_key` is how a later fact finds the answers it settles (KNP-2 §6.2, ADR-0007).
  T0 computes it by binding the question to the fields a rule declares. T1 copies it from
  the example it answers from. T2 and T3 left it null, and KNP-2 §2.1 recorded that as a
  limit of the design: "those receipts are simply never settled". As a result, the tier that
  most needs correction was the one that never got corrected, and T1 was trained on T3
  answers that reality could not label (STATUS weakness #5). The self-improvement direction
  in `docs/ideas/2026-09-22-self-improving-pivot.md` needs labels on model-tier answers
  before anything else.

  A grounded model answer names its subject in a form the node already understands. It
  cites silver events (T3 declines when every citation is fabricated, W37 #25). Each cited
  event has a contract, and a settling contract declares the fields its settling fact is
  keyed on.

Options considered:
  A. **Derive the key from the cited events' settling contracts. Use it only when the
     citations name exactly one subject.** Chosen.
  B. **Derive it from the question** (hash of the question shape or normalised text).
     Rejected: not explored because a question hash cannot match any field a settling
     event carries, so reality could never find the receipt. It would add a key that
     settles nothing.
  C. **Take the first citation's subject when the citations name several.** Rejected: not
     explored because a fact about one cited subject does not say whether an answer
     spanning two held up. A wrong settlement is a wrong training label, and ADR-0007 exists
     to keep those out of the student.
  D. **Make `settle_key` a list.** Rejected for now: `settle_key` is in `SIGNED_FIELDS`, so
     changing its type breaks the ledger format. That needs its own ADR and evidence that
     multi-subject answers are common enough to matter. Revisit below.
  E. **Leave it null and rely on caller outcomes or a shadow teacher.** Rejected as the
     whole answer: those judge one receipt by id. Reality settlement is the only source that
     is free and unarguable (ADR-0007), and it is keyed. The shadow teacher still comes
     next, for answers that have no subject.

Decision:
  A. `ledger.outcomes.settle_key_from_citations(contracts, store, citations)` returns the
  single subject's key or null. `serve._receipt` calls it only when the tier result carries
  no key of its own. A rule's bound key is more specific and is never overridden. A bridged
  answer cites the neighbour's events, which are not in local silver, so it stays null here.
  The neighbour's own receipt carries the key.

Consequences:
  - A T2 or T3 answer grounded in one subject is settled by reality exactly as a T0 answer
    is. Its outcome labels the T1 examples trained from it.
  - Answers that span subjects, or cite only non-settling schemas, stay null. The share of
    those receipts is now the measurable gap that the shadow teacher closes.
  - No change to the ledger format. KNP-2 §2.1 is updated to describe the derivation.

Revisit when:
  More than a quarter of grounded model answers on a real cell cite more than one subject.
  Option D then earns its breaking change.
