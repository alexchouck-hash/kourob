# AGENTS.md

Conventions for every agent session in this repository. This file is authoritative.
`CLAUDE.md` is a pointer to it. If this file and a prompt disagree, this file wins unless
the human says otherwise in the session.

## 1. What this project is

KouroB is a Python package and template for building metered, provenance-tracked,
self-specializing **nodes** that agents and other nodes attach to through MCP, A2A, and
REST. The repo is the first node. Read `docs/brief/07-kourob-development.md` for the full
design; read `GOAL.md` for what success means.

Key shape (brief section 3): a request is authenticated and metered, scope-checked,
gated (writes) or tier-cascaded (reads), answered with `{data, rendered, citations,
receipt_id}`, receipted into a hash-chained signed ledger, and logged. The request log is
itself the dataset the `evolve` loop reads to make the node cheaper.

## 2. Session rituals

These are mandatory. A PR that skips them is blocked by the reviewer.

### Start

1. Read `AGENTS.md`, `GOAL.md`, `docs/DEFAULTS.md`.
2. Read the claimed Beads task: `bd show <id>`. Claim it: `bd update <id> --status in_progress`.
3. Read the last three files in `docs/handoffs/`.
4. Grep `docs/adr/`, `docs/experiments/`, `docs/spikes/` for the task's keywords.
   **List what you found in the PR description before writing code.** If you found
   nothing, say "grepped adr/experiments/spikes for <keywords>: no prior art".
5. State the plan in the PR description before the first commit.

### End

1. Write `docs/handoffs/YYYY-MM-DD-<agent>-<task>.md` with: done, not done, surprises,
   open questions, and **exact resume commands**.
2. Write an entry in `docs/experiments/` for anything tried and abandoned.
3. Write or update an ADR for any decision (template in section 6).
4. `bd close <id>` or `bd update <id>` with what is left.
5. Open a PR. **Never merge your own work.**

## 3. Decide, do not ask

The full policy is `docs/DEFAULTS.md`. Summary: if a choice is reversible and inside the
task's scope, make it, record it in the PR under `## Decisions made without asking`, and
continue. Escalate to the human only for: irreversible or external side effects (deleting
data, spending money, publishing), contradiction with `GOAL.md` or an accepted ADR, two
spikes disagreeing on something that moves a `GOAL.md` metric, or a change touching keys,
payments, or minors' data.

## 4. Code rules

- **Nothing writes to `data/silver` or `data/gold` except `gate.py`.** CI greps for it.
- **Training code never references `data/gold` paths except through `evals/`.** CI checks.
- **Every port handler returns `{data, rendered, citations, receipt_id}`.** No exceptions,
  including errors and referrals.
- **Every model call goes through `runner/`** so it is logged to `logs/calls.parquet` with
  tier, tokens, and cost. A direct vendor SDK import outside `runner/adapters/` is a CI
  failure.
- **Ports are thin; logic lives in the core modules.** A file in `src/kourob/ports/` over
  300 lines is a smell and the reviewer may block on it.
- **Small PRs**: one Beads task each, under 400 lines changed where possible. Docs-only
  and tests-only PRs may be auto-approved by the reviewer agent.
- **Commit style**: `type(scope): summary`, types `feat fix docs test refactor chore adr`.
- Every acceptance criterion in brief section 12 is a test, written **before** the
  implementation.

## 5. Roles

| Role | Owns |
|---|---|
| **Planner** | Turns milestones into Beads tasks with acceptance criteria and context pointers |
| **Implementer** | One task, one branch, one worktree |
| **Reviewer** | A *different vendor* than the implementer; may only block with a cited reason |
| **Skeptic** | Attacks the design of M3–M5 before implementation: leakage, forged receipts, route poisoning, split thrash |
| **Archivist** | Runs the weekly loops (lint, prune, reflect) and files the digest PR |
| **Trainer** | Frontier sessions that build example nodes (`kourob train`) |

## 6. ADR template

Every design choice marked **ADR** in the brief gets a file in `docs/adr/` *before*
implementation. Never implement an alternative silently.

```
# ADR-NNNN: <title>
Status: proposed | accepted | rejected | superseded-by-NNNN
Date:
Context:
Options considered:
  A. ... (spike: docs/spikes/... or "not explored because ...")
  B. ...
Decision:
Consequences:
Revisit when:
```

**No option may be rejected without a spike or an explicit "not explored because" line.**

## 7. Where things live

```
docs/brief/      the design documents, unchanged, as source material
docs/protocols/  KNP: the wire contracts between nodes. Specs, not decisions
docs/integration/ how existing systems become nodes, one file per set
docs/adr/        decisions, numbered, with the template above
docs/spikes/     time-boxed investigations that inform an ADR
docs/experiments/ things tried and abandoned, with the reason
docs/ideas/      proposals that do not move a GOAL.md metric
docs/handoffs/   one per session, mandatory
docs/decisions/  decisions too small for an ADR, dated, one file per week
docs/runbooks/   how to operate a node in production
src/kourob/      the package
template/        what `kourob init` lays down
examples/        kourob-node (dogfood), tennis-node, ui
evals/           acceptance evals that gate milestones
tests/           unit and integration tests
```

## 8. Milestones

M0 skeleton · M1 ingest and answer · M2 knowledge, packs, attach, dogfood ·
M3 node-to-node (A2A, referral, bridge, routes) · M4 metering, pricing, evolve, split ·
M5 distill, cost curve, reference UI. Acceptance criteria are in brief section 12 and in
Beads (`bd ready`).

## 9. Beads

The block below is generated and maintained by `bd`. Do not edit it by hand; `bd` will
overwrite it. Where it and section 2 of this file disagree, **section 2 wins**: this
project requires a handoff file and an ADR, which bd's generic protocol does not know
about.

Issue prefix is `kb`. `bd ready` is the entry point for every session.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
