# ADR-0007: Outcomes are a ledger record, and the evolve objective is cost per *settled* request
Status: accepted
Date: 2026-09-10

Context:
  Brief section 6.3 says "a pull that hit T3 becomes a labeled example for T1". It does not
  say where the *label* comes from. A receipt records what the node answered, not whether
  the answer was any good. Training T1 on unlabelled T3 output teaches the student to
  imitate the teacher including its mistakes, which brief section 15 already names as a
  risk and then mitigates only with gold sets.

  Gold sets are expensive and static. The request log is free and grows. Without a way to
  label the request log, the evolve loop can make a node cheaper but not better, and
  cheaper-but-wrong is the failure mode that kills this design: the cost curve in GOAL.md
  would be met by a node that has learned to be confidently useless.

Options considered:
  A. **Nothing. Train on gold only.** What the brief implies today. Rejected: gold does not
     grow with traffic, so the node stops improving exactly when it starts being used, and
     the "each pull leaves the node more useful" claim in section 6.3 is not delivered.
  B. **Infer labels from tier agreement.** Treat an answer as correct when T1 and T3 agree.
     Not explored with a spike because agreement measures similarity to the teacher, which
     is what distillation already optimises; it cannot detect a mistake both tiers make, and
     those are the mistakes that matter.
  C. **Outcomes as a separate feedback store.** A side table of corrections, outside the
     ledger. Not explored with a spike because it splits provenance: a caller could then be
     shown an answer whose correction exists but is not reachable from the receipt.
  D. **Outcomes as a record in the same hash chain, referencing a receipt.** Signed,
     append-only, never editing the receipt it judges. Four sources with different trust:
     caller, downstream, human, reality.

Decision:
  D. Append `outcome` records to the same per-node hash chain as receipts (KNP-2 section 6).
  An outcome names the receipt it judges, a verdict
  (accepted, corrected, rejected, superseded, unresolved), a source, and evidence. It never
  edits or deletes the receipt.

  Every schema declares an `outcome_window` and, where applicable, the schema whose arrival
  settles it (`settles_against`). A receipt past its window with no outcome is `unresolved`.

  The evolve loop's objective becomes **cost per settled request**, not cost per request,
  subject to three constraints: quality multiplier above a floor, non-decreasing derived
  share, and no scope change without a human (KNP-5 section 1).

Consequences:
  - The ledger grows faster: one outcome per settled request on top of one receipt per
    request. Retention for outcomes matches receipts (forever), because an outcome is the
    only durable record that an answer was wrong.
  - **Unverifiable work cannot get cheap.** A cluster whose settle rate is zero cannot
    promote past T2 and cannot earn a quality multiplier (KNP-3 section 3). This is a real
    constraint on which domains suit a node, and it should be stated to anyone choosing one.
  - `source: reality` — a later event settling an earlier answer — is the only source that
    is free, honest, and unarguable. Domains where answers are eventually settled by data
    the node ingests anyway are strictly better node candidates. The tennis prediction node
    in docs/integration/tennis-set.md is chosen for exactly this.
  - A caller can be shown an answer *and* its correction from one receipt id, which is what
    makes `kourob trace` honest rather than flattering.
  - Self-reported outcomes are strategic. `source: caller` is recorded at a lower weight,
    never rejected — a third party noticing an error is useful even when it cannot be
    trusted. Weighting is a policy, not a protocol rule, and it will need tuning.

Revisit when:
  A node accumulates enough caller-sourced outcomes for gaming to be measurable, or the
  outcome record needs to carry a payload rather than a reference to an evidence event.
