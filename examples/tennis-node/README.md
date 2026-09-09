# tennis-node

**Lands in M3.** A real node over the Match Charting Project data, owning `shot.v1`.

It exists for three reasons:

1. It is the referral target in the router test (`evals/router_test.py`): kourob-node
   receives a tennis question, bridges here once, and hands the caller a direct route.
2. It carries the cost curve in `evals/cost_curve.py`: 30 days of replayed traffic, cost
   per request down fivefold, T0+T1 serving 80 percent.
3. It is a node nobody on this project is an expert in, which is the honest test of
   whether a trainer session can build one.

Data: the Match Charting Project. **Not vendored** — the data carries its own terms and is
DVC-referenced (ADR-0002, Consequences). The `shot.v1` contract in
`evals/gate_fixtures/schema.odcs.yaml` is the same shape this node uses.
