# 2026-09-10 · claude-code · M1 runs end to end

Task: refine the design, build the infrastructure that makes it run, and connect it to the
neuron framing — easy to connect, self-contained, evolving, trash-collecting.

## Done

### Specs — four more, and one fix the code forced

- **KNP-6 tap**: CloudEvents over SSE, three topics (`events`, `answers`, `changes`), replay
  from any id, metered as a read. Many custom UIs over one typed, receipted flow.
- **KNP-7 autonomy**: the A0–A4 ladder, earned by evidence and revoked by breach. **A node
  may become better at its job; it may never change what its job is**, at any level.
  Autonomous change is paid from the node's own balance, so a node nobody calls cannot fund
  its own improvement and stops. `kourob tend` is the cycle; every auto-applied change is an
  event carrying its own inverse, and a change with no recorded inverse is never
  auto-applied.
- **KNP-8 cells**: names the actual problem — building with an LLM produces unbounded growth
  because nothing tells a component it is full. A cell is one agent's whole working set,
  nothing crosses its membrane by import, and its size ceiling makes a PR fail rather than a
  limit rise.
- **KNP-9 synapses**: connecting is one command and one row, never an import. Hebbian route
  strength, rising on success and decaying always. Garbage collection of six classes with
  two absolute exemptions: **events and receipts are never collected.**
- **A fourth determinism class, `declared`** — found by a test, not by design.

### Code — M1 runs

`kourob init demo`, then `kourob ingest demo/fixtures/events.jsonl`, then
`kourob query "what is a bridge"` returns a cited, receipted, `derived` answer out of the box.

| Module | State |
|---|---|
| `identity.py` | ed25519, real `did:key:z6Mk...`, base58, JCS canonical signing |
| `manifest.py` | full model including the cell ceiling, autonomy, prune policy |
| `store/parquet_duckdb.py` | append, named-param SQL, get, scan, partitions, compact, stats |
| `schema/loader.py` | the ODCS subset the gate needs, every violation not just the first |
| `gate.py` | all seven steps, quarantine with the rejecting step, dedupe surviving restart |
| `ledger/chain.py`, `verify.py` | hash chain, signing, verify, trace, tamper helper |
| `tiers/` | Tier interface, T0 rules as regex plus SQL, cascade logging every attempt |
| `serve.py` | the one place an answer is built, so the one place invariants hold |
| `ports/mcp.py` | four tools, full envelope on every path including unknown tools |
| `node.py` | the cell handle: `open_node`, `init`, `health`, `cell_size` |

**All six M1 acceptance criteria pass.** 59 passed, 15 xfailed (M2–M5 only). The gate scores
**precision 1.000, recall 1.000** on `evals/gate_fixtures/` against a required 0.95, and each
rejection lands on the exact step the fixture predicted.

## Not done

- **Runner and T3** (`kb-6om`, `kb-458`). No model call goes anywhere yet: M1's cascade is
  T0-only, which is why `query` refuses rather than falling through to a model.
- **W3C PROV export** (`kb-x0k`, reopened after I closed it too eagerly — `trace` works, the
  export does not).
- **Schema codegen and breaking-change detection** (`kb-4m5`): the small reader is in, the
  `datacontract-cli` half is not.
- **The MCP server itself.** `handle()` is done and tested; stdio transport is not, so no
  agent can attach yet.
- **`kourob tend`, `connect`, `cell seams`** — specified in KNP-7/8/9, not built.

## Surprises

1. **A test found a hole in KNP-0.** `list_schemas` had nothing to cite and the grounding
   invariant called that a violation. It was right to: the spec had no way to say "the node
   is describing itself". That is what writing the acceptance tests first is for.
2. **PII regexes eat ISO timestamps.** A pattern loose enough to catch `+1 612 555 0134` also
   matches `2026-01-25T04:31:02Z`, which dropped gate precision to 0.600. Fixed by scanning
   **free text only** — undeclared fields and unconstrained strings. Structured fields are
   where PII is declared, not smuggled.
3. **Git Bash here truncates commands at about 8 KB**, which surfaces as an unmatched-quote
   parse error, and a backslash-n inside a Python heredoc reaches the file as a real newline.
   Both cost time. Split long heredocs; avoid escapes in generated string literals.
4. **`bd` refuses to close a task whose dependencies are open.** Correct, and it caught me
   closing the gate task while its schema task was still half-done.

## Open questions

1. **`kourob.org` still unregistered** — the extension URIs assume it.
2. **T0 rules are regex plus SQL.** That is genuinely what KNP-5 section 3.3 would mine, but
   the regex half is brittle: "what is a bridge" needed a rewrite the first fixture did not
   survive. Before M5 mines rules automatically, decide whether question-matching stays regex
   or becomes a classifier. Mining a bad regex at scale is worse than not mining.
3. **Cost per *settled* request may make 5x unreachable** in slow-settling domains. Still
   open from the last session; better decided before M5 than during it.
4. **Branch protection still blocks you merging your own PRs.**

## Resume

```bash
cd C:/Users/houck/kourob
git checkout feat/protocols-and-evolution
uv run pytest -q
uv run kourob init /tmp/demo
uv run kourob ingest /tmp/demo/fixtures/events.jsonl --node /tmp/demo
uv run kourob query "what is a bridge" --node /tmp/demo
uv run kourob doctor --node /tmp/demo
uv run kourob ledger verify --node /tmp/demo
bd ready
```

Next, in dependency order: `bd show kb-6om` (runner) unblocks T3 and everything metered;
`bd show kb-p4q` (outcomes) unblocks all of M4 and M5.
