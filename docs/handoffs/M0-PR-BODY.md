# PR body for M0, ready to open

There is no GitHub remote yet (brief section 14 is a human step and publishing is an
escalation under `docs/DEFAULTS.md`). This file is the PR description for
`chore(m0): repository skeleton, conventions, and M1 acceptance tests`, filled in against
`.github/PULL_REQUEST_TEMPLATE.md`, so it can be opened without redoing the work.

## Beads task

Milestone M0 itself (brief section 12). The M1 tasks it creates are `kb-uca`, `kb-4m5`,
`kb-b0r`, `kb-1xp`, `kb-2k0`, `kb-j89`, `kb-6om`, `kb-fo8`, `kb-458`, `kb-4gw`, `kb-3bm`,
`kb-x0k`.

## Prior art found

- grepped `docs/adr`, `docs/experiments`, `docs/spikes` for store, license, cli, ledger:
  **no prior art** — this is the first session, those directories did not exist.
- `docs/brief/01` to `06` were not supplied. See `docs/brief/README.md`.

## Plan

Brief section 16, steps 1 to 7.

## Acceptance criteria, as tests

| Criterion (brief section 12, M0) | Test |
|---|---|
| `uv run kourob --help` lists all top-level commands as stubs | `tests/test_cli.py::test_help_lists_every_expected_command`, `::test_no_undeclared_commands`, `::test_stubs_exit_two_and_name_their_milestone` |
| CI green on an empty test suite plus lint | `.github/workflows/ci.yml`; `uv run ruff check .`, `ruff format --check .`, `pytest -q` → 30 passed, 16 xfailed |
| `bd ready` returns the M1 tasks | `bd ready` → kb-6om, kb-b0r, kb-uca, kb-4m5 (the rest are blocked by the dependency graph, which is the point) |

M1's criteria are written as strict-xfail tests in `tests/test_m1_acceptance.py`; M2 to M5
in `evals/`.

## Decisions made without asking

See `docs/decisions/2026-W37.md`. In short: strict-xfail for not-yet-implemented
acceptance tests; the section 4 rails are pytest rather than CI greps; typer for the CLI;
stubs exit 2; every module declares `__milestone__`; the silver/gold rail forbids naming
the path, not just writing it; bd's managed block lives in AGENTS.md.

## ADRs

- `docs/adr/0001-store-interface.md` — accepted
- `docs/adr/0002-license-apache-2.0.md` — accepted

ADR-0003 (ledger), 0004 (price), 0005 (split) belong to M4 and are deliberately not
written: writing them now would mean rejecting options without spikes.

## Handoff

`docs/handoffs/2026-09-09-claude-code-m0-skeleton.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
