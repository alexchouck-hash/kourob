# 2026-09-15 — claude-code — a document served by a node (`site/maude.html`)

Task: publish a method note on the KouroB site that is produced by a live KouroB node rather than
written by hand. Ad hoc, no Beads task claimed up front; `kb-agx` was filed from what the build found.

## Grep of prior art

Grepped `docs/adr/`, `docs/experiments/`, `docs/spikes/` for `markdown`, `in-port`, `compile`,
`dogfood`, `export`. Prior art found and followed:

- `examples/kourob-node/README.md` — the three-command recipe (`init`, `ingest --from-markdown`,
  `loop run compile`). This node is the same recipe pointed at a different document.
- `examples/trooth-network/export_web.py` — the pattern of exporting a ledger as the exact canonical
  bytes each record was signed over, so a browser verifies rather than believes. `export_site.py`
  reuses its `_records` shape and `site/maude.js` reuses `network.js`'s b58/did:key/WebCrypto path.
- `docs/decisions/2026-W37.md` #73 — page per key, which is why the source is one claim per heading.

## Done

- **`examples/maude-method-node/`** — two source files and a README. Nothing generated is committed.
  - `source/maude-distinct-events.md`: 23 headings, one paragraph each, on counting distinct events
    in FDA MAUDE data. Method, validation plan, acceptance floor, and the limits the numbers carry.
  - `export_site.py`: builds the node from scratch in a temp dir (`init` → markdown in-port →
    compile), asks all 23 topics through `serve.answer`, and writes `site/maude.json`: the node's
    `did:key` and genesis anchor, every answer with tier, determinism, citation, receipt, price and
    latency, the events cited, and all 23 ledger records as signed bytes plus signature.
- **`site/maude.html` + `site/maude.js`** — the page, rendered entirely from that JSON. Each claim
  shows the question asked, the tier that answered, the rule that bound it, the event it cited, the
  `file#heading` that event came from, the receipt, the price and the latency. The verify panel
  checks all 23 signatures and the whole `prev` chain with WebCrypto, and a second button flips one
  digit so a reader can watch it fail.
- Registered in `site/sitemap.xml`, `site/llms.txt`, and the nav on `index.html`, `examples.html`
  and `maude.html`.
- **`kb-agx`** filed: the markdown in-port silently loses every paragraph after the first under a
  heading (below).

## Measured

- 23 events held, 23 answers served, 23 signed receipts, 0 quarantined.
- Every answer T0 `derived`, bound by `rule:note-lookup`, 0.00005 credits each.
- Browser verification: 23/23 hash chain, 23/23 ed25519 signatures, in the Chromium preview.
- Tamper button: the edited record's signature fails and the next record's `prev` no longer matches.
  It does **not** cascade through every later record, because each one re-anchors on its own bytes.
  An earlier draft of the copy claimed it did; that line was corrected before commit.

## Surprises

1. **The gate ate two thirds of the document.** The in-port gives every paragraph under a heading
   the same `note.v1` topic *and* the same `ts`, and the gate keys `note.v1` on `(topic, ts)`. A
   24-paragraph draft ingested as 16 accepted, 8 quarantined as `dedupe.key`, with no error: the
   node just held less than the document said. The source is now one paragraph per heading, and
   `export_site.py` raises rather than exporting a partial node. `examples/kourob-node/README.md`
   still claims every paragraph becomes a push, which is wrong. Filed as `kb-agx`.
2. **`pages/index.md` renders `{{ scope_summary }}` unsubstituted** in its `# Index:` heading. Not
   filed; noticed while reading compile output and not on this task's path.
3. `kourob init` correctly refuses to rotate an existing key, so re-running it over a node directory
   whose `.kourob/keys/` survived a partial `rm` keeps the old identity. Worth knowing when rebuilding.
4. Another session's preview server was already serving `site/` on 4400, so verification used it
   rather than starting a second one.

## Not done

- **The page is not live.** `main` has no `site/` directory and the `github-pages` environment only
  accepts deployments from `main`, so nothing here reaches the live site until `feat/public-site`
  merges. PR #2 is `MERGEABLE` but `BLOCKED`: `main` requires one approving review with
  `enforce_admins` on, so the owner cannot self-merge. Unchanged from the 2026-09-14 handoff.
- No live querying from the page. It is static by necessity until the HTTP transport (`kb-imt`).
- No test builds this node the way `tests/test_dogfood.py` builds the dogfood one, so the example
  can drift from the code. That is the obvious next item and it is small.

## Resume

```bash
cd C:/Users/houck/kourob-site
uv run python examples/maude-method-node/export_site.py --out site/maude.json
python -m http.server 4400 --directory site   # then open http://localhost:4400/maude.html
gh pr view 2 --json mergeable,mergeStateStatus
```
