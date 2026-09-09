# DEFAULTS.md

Decide, do not ask. This file exists so an agent session never stalls on a question the
project already has an answer to. If a situation is not covered here, choose, record the
choice in the PR under `## Decisions made without asking`, and **add it to this file in
the same PR**.

## Naming and format

- Python: `snake_case` for modules, functions, variables; `PascalCase` for classes.
- Files and CLI flags: `kebab-case`. CLI subcommands: `kebab-case`.
- Timestamps: ISO 8601, UTC, `Z` suffix. Never local time, never naive datetimes.
- Ids: ULIDs, prefixed by kind — `evt_`, `rcpt_`, `nd_`, `req_`, `tsk_`.
- Node identity: `did:key:z6Mk...` over an ed25519 public key.
- Hashes: `sha256:<hex>`.

## Dependencies

- A new dependency is allowed without an ADR if it is **permissively licensed**
  (Apache-2.0, MIT, BSD, ISC, PSF) **and under 5 MB installed**. Note it in the PR.
- Anything copyleft, anything over 5 MB, or anything that becomes a load-bearing
  interface (a store backend, a model runtime, a task tracker) needs an ADR.
- Pin with `uv`. Lockfile is committed.

## Tests

- `pytest`. Every acceptance criterion in brief section 12 is a test.
- Fixtures in `tests/fixtures/`. Eval fixtures in `evals/`.
- **No network in unit tests.** Model calls in tests are mocked through the runner's
  `local` adapter.
- Tests for a milestone that is not yet implemented are written first and marked
  `@pytest.mark.xfail(strict=True)` with the milestone in the reason, so CI is green on
  the current milestone and turns red the moment the feature lands without the marker
  being removed. Remove the marker in the PR that implements the feature.

## Ambiguity

- Choose the **stricter** reading. A stricter scope, a stricter schema, a stricter refusal.
- Record it under `## Decisions made without asking`.

## Schemas

- ADR first, then implement. Run `datacontract changelog` and paste the output in the PR.
- Breaking changes to a published schema require a new major version and a migration note
  in `docs/runbooks/`.

## Data and safety rails

- Only `gate.py` writes `data/silver` and `data/gold`. Everything else is a CI failure.
- Training code reaches `data/gold` only through `evals/`.
- A node without a gold set cannot enable T1. This is enforced in code, not by convention.
- Receipts hash requests and responses; they never store them.

## Escalate to the human only when

1. The action is irreversible or has an external side effect: deleting data, spending
   money, publishing a package or a repo, sending a message.
2. The change contradicts `GOAL.md` or an accepted ADR.
3. Two spikes disagree on something that moves a `GOAL.md` metric.
4. The change touches keys, payments, or minors' data.

Everything else: decide, record, continue.
