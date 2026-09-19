# 2026-09-10 · claude-code · compile and lint

Task: `kb-afx`, the loops half. The dogfood node is the other half and follows.

## Done

- **`knowledge/compile.py`** — pages from silver, regenerated every run, one page per
  contract key value (`note.v1` groups by topic), every claim line ending in `[evt_...]`.
  Page metadata is an HTML comment and the scope summary lives in the index heading, because
  a sentence *about* the page is an uncited claim to the linter — correctly. Compile owns
  what it generated: stale generated pages are removed, hand-written ones are left for lint.
- **`loops/lint.py`** — `uncited_claim` (with the line), `orphan_citation` (an id not in
  silver), `hand_edited` (no compile header). `lint_node` is what `tend` runs; a failure
  halts it, since nothing autonomous should run on top of a knowledge base lint would not
  pass.
- **`get_page`** over MCP serves the compiled page with its citations; the index comes back
  `declared` (the node describing its own pages). **`kourob loop run compile | lint`**.
- The M2 lint eval passes for real; `tests/test_knowledge.py` covers the rest.

## Surprises

1. **The linter caught the compiler.** "Schema `note.v1`. 1 claim(s)." on every page was an
   uncited claim. It took one lint run over compile's own output to find, and the fix
   (metadata as comments) removed a lint special case rather than adding one.
2. **The lint eval's fixture id was not a ULID**, and the citation regex was pinned to ULID
   length, so the cited line flagged and the uncited one did not. Any `[evt_...]` is now a
   citation; existence is the orphan check's job.

## The dogfood node, also done

- **`ports/files.py`** — markdown to `note.v1`: one push per paragraph under a heading,
  `source = file#heading`, code fences and tables skipped, fragments under 40 characters
  dropped. `kourob ingest <path> --from-markdown`.
- **`tests/test_dogfood.py`** builds `kourob-node` from `docs/protocols/` on every run
  (hundreds of paragraphs, lint-clean pages, inside the cell ceiling) and answers *"what is
  a bridge and when does a node stop bridging"* with a citation to a bridging paragraph in
  this repository. `examples/kourob-node/README.md` is the three-command recipe; nothing
  generated is committed.

## Not done

- **Packs** (`kourob pack`) and the real fresh-agent eval (a live Claude Code session).
- **Contradiction and stale flags** — the brief lists them; only uncited/orphan/hand-edited
  exist. Contradiction needs a per-key comparison the gate already does at ingest.

## Resume

```bash
cd C:/Users/houck/kourob && git checkout feat/protocols-and-evolution
uv run pytest tests/test_knowledge.py -q
D=/tmp/demo && uv run kourob init $D && uv run kourob ingest $D/fixtures/events.jsonl --node $D
uv run kourob loop run compile --node $D && uv run kourob loop run lint --node $D
```
