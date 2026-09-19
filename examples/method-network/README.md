# method-network

Five cells assemble one document. Four own a domain and answer only from it; the fifth holds
nothing and knows who does. `site/maude.html` is the result: a method note on counting distinct
events in FDA MAUDE data where every sentence carries the cell that vouched for it, the event it
cites, the route the question travelled, and a signed receipt.

Nothing generated is committed: the cells land in `cells/`, gitignored. The source documents and
two scripts are the whole truth. `TODO-offer.md` lists the 10xAnd offer terms the page still owes.

| Cell | Owns | Refuses |
|---|---|---|
| `fda-facts` | what the dataset structurally is | method, results, policy |
| `maude-method` | how distinct events are estimated | whether it works |
| `eval-gates` | targets, results, and the gap between them | how the method works |
| `claims-policy` | what any output may and may not say | facts, method, results |
| `method-desk` | **nothing** | everything, by referring it onward |

## Build it and ask it

```bash
uv run python examples/method-network/build.py
uv run kourob query "what is the-precision-target" --node examples/method-network/cells/method-desk
uv run kourob query "which device is safer" --node examples/method-network/cells/method-desk
```

The first goes to `eval-gates`, which is the only cell allowed to say whether the method works,
and its answer is that 0.85 is a target and nothing has been measured. The second is refused:
no cell holds a safety comparison, the desk knows none that does, and the refusal is receipted
like any other answer.

## Rebuild the page's data

```bash
uv run python examples/method-network/export_site.py --out site/maude.json
```

Builds the network from scratch in a temporary directory, puts every section question to the
desk, follows the routes the desk hands back, and writes each cell's ledger as the exact
canonical bytes it signed. `site/maude.js` checks all five chains in the browser.

## What the routing shows

The desk bridges for a caller **once** per neighbour and refers after that, so the export sees
both halves of the referral design in one run:

```
one-event-several-reporters      bridge    2 hops   method-desk
follow-ups-are-separate-records  in_scope  1 hop    method-desk > fda-facts
no-denominator                   in_scope  1 hop    method-desk > fda-facts
```

The first question is carried. Every later one is answered with a route, and a caller that keeps
the route stops paying for the middle hop. That is GOAL.md metric 5, visible on a page.

Routing patterns are **derived from the source headings** by `desk_routes()` rather than
maintained beside them. A hand-written pattern list drifts the first time somebody renames a
heading, and the failure is silent: the desk stops referring and tries to answer from a store it
does not have.

## What this does not demonstrate

- **No model wrote anything.** Every claim is a T0 lookup against a stored note, which is why
  each one can be diffed against the source line it came from. Connective prose at T3 is wired
  behind `--model-url` and is only attempted when an ollama-compatible server answers; with none,
  the export records that fact and the page states it. See "Who wrote this" on the page.
- **The page is static.** The cells ran when the export ran. Live querying needs the HTTP
  transport (`kb-imt`); today cells talk only on disk.
- **No FDA data has been processed.** The network holds the method, not a run of it. Precision
  and recall are design targets, labelled as such, because no validation set exists.

## Two bugs this example found

- **`kb-gpc`**: a cell holding nothing cannot run a note-lookup T0 rule. T0 binds `schema_ref`
  against an empty `silver`, which DuckDB rejects because an empty store has no columns to bind,
  so the desk crashes instead of missing cleanly. Worked around here by removing the rule from
  the desk, which is correct for a desk anyway.
- **`kb-b5x`**: a receipt signed while a credit field held a Python `int` could never be verified
  again, because the store reads that column back as a float and `0` and `0.0` do not sign to the
  same bytes. Refusals hit it every time, since a refusal costs exactly `0`. Fixed in
  `signed_view`, with `tests/test_ledger_numbers.py` as the reproduction.
