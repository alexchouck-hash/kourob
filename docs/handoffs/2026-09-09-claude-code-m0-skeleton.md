# 2026-09-09 · claude-code · M0 skeleton and conventions

Task: brief section 16, "First session checklist for Claude Code", and milestone M0.

## Done

- **Layout** from brief section 11, complete, including `template/` (section 8),
  `examples/` placeholders, `evals/`, `tests/`, `.github/`.
- **`AGENTS.md`** from section 13; **`CLAUDE.md`** as the one-line pointer;
  **`GOAL.md`** from section 1; **`docs/DEFAULTS.md`** from 13.3; **`docs/GLOSSARY.md`**
  from section 2.
- **ADR-0001** (store interface, Parquet + DuckDB default) and **ADR-0002** (Apache-2.0),
  both accepted, both with every rejected option carrying a reason. ADR template and index
  in `docs/adr/`.
- **`pyproject.toml`**: package `kourob`, CLI entry `kourob`, ruff and pytest configured,
  `xfail_strict = true`.
- **CLI**: 21 top-level commands, every one named in the brief. Unimplemented commands
  exit 2 and print the milestone that will implement them.
- **CI** (`.github/workflows/ci.yml`): ruff check, ruff format check, `kourob --help`,
  pytest, plus contract-lint and ledger-verify steps that activate when the files they
  need exist. **`loops.yml`** with the schedules from section 6.1.
- **Beads** initialised, prefix `kb`, 12 M1 tasks with acceptance criteria, context
  pointers, and a dependency graph. `bd ready` returns the four unblocked ones.
- **Tests**: 30 passing (CLI honesty, the AGENTS.md section 4 rails), 16 xfail (M1
  acceptance in `tests/`, M2–M5 acceptance in `evals/`).
- **Gate fixtures**: `evals/gate_fixtures/` with 10 accept and 15 reject cases across every
  gate step, plus 4 unparseable lines, and the `shot.v1` ODCS contract they validate
  against.

## Not done, deliberately

- **No implementation.** M0 is the skeleton and the contracts. The M1 tests are written and
  red, which is the point.
- **`examples/kourob-node` is a README only.** It becomes a real node in M2. An example
  that claims to work and does not is worse than no example.
- **ADR-0003, 0004, 0005 not written.** They belong to M4 and writing them now would mean
  rejecting options without spikes.
- **GitHub repo not created and no PR opened.** Brief section 14 is a human step; it
  publishes, which `docs/DEFAULTS.md` says to escalate. Commands are below.

## Surprises

1. **`bd init` rewrote `CLAUDE.md` and `AGENTS.md`.** It appended its managed block to
   both and added a duplicate copy of the same guidance under a "BEADS CODEX SETUP"
   marker. Resolved by restoring `CLAUDE.md` to the one-line pointer the brief specifies,
   deleting the duplicate block, and adding `AGENTS.md` section 9 to say that section 2
   wins where the two disagree. Expect `bd setup <tool>` to try this again.
2. **`bd init` made its own git commit** before the skeleton was committed, so the first
   commit in history is `bd init` rather than the skeleton. Left alone rather than
   rewritten.
3. **`@beads/bd` does not install from npm on Windows** — its postinstall fails to fetch
   the native binary. Installed from the GitHub release instead, checksum verified against
   `checksums.txt` (`1f00c29c...b2feb`). See "Resume" for the command.
4. **Brief documents 01 to 06 were not supplied.** 07 is self-contained for M0 and M1.
   `docs/brief/README.md` records what is missing and which milestone will want it.
5. Typer 0.27 vendors click, so `import click` fails in a test even though the CLI works.

## Open questions for the human

1. **GitHub org and repo name** for brief section 14 (`gh repo create <org>/kourob`).
   Nothing has been published.
2. **`docs/brief/01` to `06`** — are they available? M5 will want 02 (distillation) for the
   gold-set discipline.
3. **The `M1 acceptance tests are xfail` decision** (see the PR). The brief says "write the
   M1 acceptance tests as failing tests" and M0 says "CI green". Strict xfail satisfies
   both: the tests are red, CI is green, and the marker cannot survive the feature landing.
   Say so if you want them plainly red instead.

## Resume

```bash
cd C:/Users/houck/kourob
uv sync --dev
uv run kourob --help          # M0 acceptance 1
uv run ruff check . && uv run ruff format --check .
uv run pytest -q              # 30 passed, 16 xfailed
bd ready                      # M0 acceptance 3
```

Next task, per `bd ready`:

```bash
bd show kb-b0r                # M1: Parquet + DuckDB store behind the Store interface
bd update kb-b0r --status in_progress
```

If `bd` is missing on another machine:

```bash
gh release download v1.2.2 --repo gastownhall/beads --pattern "beads_1.2.2_windows_amd64.zip" --pattern checksums.txt
sha256sum -c checksums.txt --ignore-missing
```
