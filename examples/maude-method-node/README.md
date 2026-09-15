# maude-method-node

One document, one node, one page. This cell holds a method note about counting distinct events
in FDA MAUDE data, and `site/maude.html` is that note rendered from a real run of it rather than
written by hand.

Nothing generated is committed here: keys are secret, Parquet is binary, pages are derived. Two
files are the whole source of truth.

| File | What it is |
|---|---|
| `source/maude-distinct-events.md` | the document the node holds, one claim per heading |
| `export_site.py` | builds the node, asks it every question, writes `site/maude.json` |

## Build and ask it yourself

```bash
kourob init examples/maude-method-node --scope "the MAUDE distinct-event method and what its numbers may claim"
kourob ingest examples/maude-method-node/source --from-markdown --node examples/maude-method-node
kourob loop run compile --node examples/maude-method-node
kourob query "what is the-acceptance-floor" --node examples/maude-method-node
```

Every topic answers at T0, because the mined note-lookup rule binds `what is <topic>` where
`<topic>` is a heading slug. No model runs, no key is needed, and nothing reaches the network.

## Rebuild the page's data

```bash
uv run python examples/maude-method-node/export_site.py --out site/maude.json
```

The exporter builds the node from scratch in a temporary directory every run, so the export is a
record of a node that existed a second ago rather than a description of one that existed once. It
writes the node's `did:key`, every answer with its tier, citation, receipt and price, the events
cited, and the whole ledger as the exact canonical bytes each record was signed over plus its
ed25519 signature. `site/maude.js` checks all of it in the browser with WebCrypto, and offers a
button that flips one digit so a reader can watch the check fail.

## One heading, one claim

The gate keys `note.v1` on topic and timestamp. The markdown in-port gives every paragraph under a
heading the same topic and the same timestamp, so the second paragraph under a heading arrives as a
contradiction of the first and is quarantined rather than stored. An earlier draft of the source
lost 8 of 24 paragraphs that way, silently as far as the page was concerned.

The document is written around the limitation: one heading, one paragraph, which is also the shape
the compile loop wants, since it emits a page per key. `export_site.py` fails loudly rather than
exporting a partial node if the gate ever quarantines anything.

## What this does not demonstrate

- **No live serving.** The page is static. The node ran when the export ran, so the questions are
  fixed and the answers are the ones that run got. Live queries need the HTTP transport (`kb-imt`).
- **T0 only.** Nothing here exercises T1 or T3. Every answer is a rule binding a stored note.
- **No FDA data.** The node holds the method, not a run of it. The precision and recall figures in
  the source are design targets, labelled as such, because no validation set exists yet.
