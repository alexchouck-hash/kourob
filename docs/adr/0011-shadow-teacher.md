# ADR-0011: The shadow teacher disputes, and never settles
Status: accepted
Date: 2026-09-22

Context:
  Reality settles an answer only when a later fact names its subject (ADR-0007, ADR-0010).
  Most cheap-tier answers never get such a fact. A mined rule or a student can drift wrong
  on exactly those answers, and nothing notices until a caller complains. The
  self-improvement direction (`docs/ideas/2026-09-22-self-improving-pivot.md`) needs a
  label source that does not wait on reality or a human. The node already has one it pays
  for: its own T3.

  ADR-0007 option B rejected "treat an answer as correct when T1 and T3 agree". Agreement
  measures similarity to the teacher, which distillation already optimises. It cannot
  detect a mistake both tiers make.

Options considered:
  A. **T3 re-answers a sample. Agreement settles as accepted, disagreement as rejected.**
     The first sketch of this idea. Rejected: its agreement half is ADR-0007 option B
     and fails for the same reason. It would let a cheap tier promote on the strength of
     resembling its teacher.
  B. **T3 re-answers a sample. Disagreement is recorded as a non-settling `teacher`
     outcome that blocks promotion. Agreement is recorded nowhere except the audit log,
     where it only lowers the sample rate.** Chosen.
  C. **T3 judges the stored answer ("is this supported by these events?").** Not explored
     because the node does not store answer text, only its hash (KNP-2 §1). A judge would
     need the answer re-rendered, which only T0 can do. Revisit if T1/T2 answers become
     reconstructible.
  D. **Route disputes to a human (T4) queue.** Not explored because T4 is a stub. A
     dispute on the chain is already what a T4 queue would read. This is additive later.

Decision:
  B. `loops/shadow.py` (`kourob loop run shadow`, nightly in the template manifest).
  - Candidates are in-scope T0/T1/T2 answers with citations, no settling outcome and no
    prior audit.
  - Each is sampled per cluster at `max(0.05, 1/(1 + agreements since the last
    dispute))`. The draw is fixed by the receipt id, so a rerun samples the same answers.
  - T3 re-answers the question with `purpose=shadow`, so auditing is metered apart from
    serving. The run stops at the credit budget.
  - If the teacher cites nothing the answer cited, that is a `dispute`: a `rejected`
    outcome with `source: teacher`, carrying the teacher's citations as evidence. If they
    overlap, that is `agree`. If T3 declines or falls below its bar, that is `abstain`.
    If T3 is unreachable, nothing is recorded and the answer stays owed.
  - `ledger.outcomes.settling_outcomes` excludes teacher outcomes. Settlement status, the
    evolve objective, cluster settle rates, T1 training and reality's own "already
    settled" check all read through it.
  - evolve declines to promote any cluster with an open dispute. A dispute stays open
    until a settling outcome on the same receipt closes it. Reality outranks the teacher.

Consequences:
  - Cheap tiers are checked continuously at a cost that grows with the log of volume, not
    with volume. The floor keeps one answer in twenty checked forever.
  - A disputed cluster stops getting cheaper until someone who can settle it speaks. The
    teacher can slow a node down but never speed one up. That is the safe direction for a
    source with no ground truth.
  - The comparator is citation overlap. It is coarse: two tiers citing the same event can
    still say different things about it. It suits grounded lookups and is too weak for
    answers that synthesise across many events.
  - `SOURCE_WEIGHT[teacher] = 0`. No ledger format change: `source` is a string field, and
    older readers see an unknown source they can ignore.

Revisit when:
  Disputes on a real cell are mostly false alarms (teacher wrong, reality agrees with the
  cheap tier), or answers become reconstructible so option C can compare content instead of
  citations.
