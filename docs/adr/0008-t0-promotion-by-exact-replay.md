# ADR-0008: A T0 rule is promoted only on exact replay over the full request log
Status: accepted
Date: 2026-09-10

Context:
  The cost curve in GOAL.md (5x down by day 30) comes almost entirely from moving traffic
  from model tiers to T0, because T0 is three to four orders of magnitude cheaper than a
  frontier call. So the question of *when a rule is good enough to promote* is the question
  of whether the project's headline number is real or fraudulent.

  Promotion to T0 also changes the receipt's determinism class from `attested` to `derived`
  (KNP-0 section 2). `derived` is a claim to a third party that they can re-run the answer
  from the events and get the same result. It is a much stronger claim than "our model said
  so", and a wrong derived answer is worse than a wrong attested one because it has been
  laundered into something that looks checkable.

Options considered:
  A. **Tolerance-based, like the other rungs.** Promote when the candidate rule matches the
     settled answers within some tolerance (say 99%), consistent with the 2-point tolerances
     used for T3 to T2 and T2 to T1. Rejected: a rule that is 99% right is not a function,
     and derived asserts that it is. The 1% become receipts that claim independent
     verifiability and do not have it.
  B. **Exact match on a held-out sample.** Cheaper to compute. Not explored with a spike
     because sampling is what tolerance is, spread differently: the failure cases for a
     mined rule are systematic (one join, one edge case), not random, so a sample is exactly
     the wrong estimator for them.
  C. **Exact match on every settled request in the cluster, with partial coverage allowed.**
     Replay the candidate over the whole historical log for that cluster. Require
     replay_exact_match == 1.0, and allow the rule to decline to answer some requests
     (coverage below 1.0), which fall through to T1.
  D. **Human review of each rule as the gate.** Not explored as the primary gate because it
     does not scale to the rule volume the cost curve requires, though it remains as the PR
     approval step on top of C.

Decision:
  C. A candidate T0 rule is promoted only when, replayed over **every** settled request in
  its cluster, it reproduces the settled answer exactly, and covers at least `min_coverage`
  (default 0.95) of the cluster's volume. Requests it does not cover fall through to T1 and
  stay attested.

  Correspondingly: **one corrected outcome on a T0 answer immediately disables the rule**
  (KNP-5 section 5). No grace period, no threshold. The rule's entire claim was that it is a
  function; one counter-example disproves it.

  Rules are mined from clusters by replay, not written by hand. The frontier model's job was
  to discover the function; hand-writing it afterwards reintroduces the error the replay
  gate exists to catch.

Consequences:
  - Fewer rules are promoted than a tolerance gate would allow, so the cost curve is slower
    to bend. This is the correct trade and the eval must be met without loosening it.
  - Partial coverage is the pressure valve: a rule that handles the common case exactly and
    declines the rest still removes most of the cost, and the declined tail stays honest.
  - Replay cost is real: a full pass over the cluster's settled history per candidate. It is
    bounded because clusters are bounded, and it runs in the weekly evolve, not inline.
  - `derived_share` becomes a headline metric alongside cost, because it is the number that
    says how much of the node a stranger can check. KNP-5 section 1 makes it a constraint,
    not just a metric: it may not decrease.
  - This gate is only as good as the outcome labels behind it, which is why ADR-0007 comes
    first. A cluster with no settled outcomes has nothing to replay against and cannot
    promote to T0 at all.

Revisit when:
  A domain appears where the settled answer is legitimately non-deterministic (a sampled or
  time-varying quantity) and the cluster still deserves a cheap tier. That needs a fourth
  determinism class, not a looser gate.
