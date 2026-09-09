## Beads task

`bd show <id>` — paste the title and the acceptance criteria here.

## Prior art found

Per AGENTS.md section 2, grep `docs/adr/`, `docs/experiments/`, `docs/spikes/` for this
task's keywords and list what you found. If nothing, say so explicitly:

- grepped adr/experiments/spikes for `<keywords>`: <what you found, or "no prior art">

## Plan

What you are going to do, stated before the first commit.

## Acceptance criteria, as tests

Which test covers which criterion. Every criterion in brief section 12 is a test written
*before* the implementation.

| Criterion | Test |
|---|---|
|  |  |

## Decisions made without asking

Per `docs/DEFAULTS.md`. Each one gets a line here, and anything reusable gets added to
DEFAULTS.md in this same PR.

-

## ADRs

Any design choice marked **ADR** in the brief has a record in `docs/adr/` **before** this
implementation. Link it:

-

## Handoff

Link to `docs/handoffs/YYYY-MM-DD-<agent>-<task>.md`.

## Checklist

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run pytest -q`
- [ ] Handoff written
- [ ] `bd close` or `bd update`
- [ ] Nothing outside `gate.py` writes `data/silver` or `data/gold`
- [ ] Every model call goes through `runner/`
- [ ] Every port handler returns `{data, rendered, citations, receipt_id}`
- [ ] I am not merging my own work
