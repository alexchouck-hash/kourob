# kourob-node (dogfood)

KouroB dogfoods itself: this project's own docs are served by a KouroB cell. `tests/test_dogfood.py`
builds it from scratch on every run and answers the M2 acceptance question — *"what is a bridge
and when does a node stop bridging"* — with a citation to the paragraph in `docs/protocols/`
that says so.

Nothing generated is committed here (keys are secret, Parquet is binary, pages are derived).
Build it in three commands:

```bash
kourob init examples/kourob-node --scope "the KouroB design and this repository"
kourob ingest docs/protocols --from-markdown --node examples/kourob-node
kourob loop run compile --node examples/kourob-node
```

Then either attach an agent —

```bash
kourob attach claude-code --node examples/kourob-node
```

— or ask it directly. With a local model running (ollama on `127.0.0.1:11434`, any small
instruct model), T3 retrieves the relevant paragraphs and answers from them, citing the events:

```bash
kourob query "what is a bridge and when does a node stop bridging" --node examples/kourob-node
```

Without one, questions that a T0 rule can bind (`what is <topic>`, where `<topic>` is a heading
slug such as `the-cell` or `hebbian-routing`) still answer at T0, and everything else is
refused with a receipt rather than guessed at.

## What it demonstrates

- **The file in-port.** Every paragraph under a heading becomes a `note.v1` push whose `source`
  is `file#heading`, so a citation resolves to a place in the docs, not just an event id.
- **Compile and lint.** `pages/` is regenerated from silver with a citation on every claim;
  `kourob loop run lint` passes on the result.
- **The cell ceiling.** The whole protocol suite fits under the template's `max_*` budget.

It exists to be small. If this cell ever needs to grow past its ceiling, that is the signal
to divide it — one cell per KNP spec is the obvious seam.
