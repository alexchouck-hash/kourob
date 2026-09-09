# kourob-node (dogfood)

**Lands in M2.** KouroB dogfoods itself: once M2 passes, this project's own docs are
served by a KouroB node living here, and the fresh-agent test in
`evals/fresh_agent_test.py` runs against it.

Scope: the KouroB design and this repository. It answers questions like *"what is a bridge
and when does a node stop bridging"* from events compiled out of `docs/`, with a citation
on every claim.

Build it with:

```bash
kourob init examples/kourob-node --scope "the KouroB design and this repository"
kourob ingest docs/ --node examples/kourob-node
kourob loop run compile --node examples/kourob-node
```

Until M2, this directory holds only this file. That is deliberate: an empty example that
claims to work is worse than no example.
