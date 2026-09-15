# Draft: the developer one-pager

Status: draft. Gate: Phase 1 desirability. Purpose: the link sent to a named developer before
the conversation in `outreach.md`. One screen, one number, one ask.

**Do not send before** the fetch API is public, or edit the "what you can use today" block to
match what actually is.

---

## Your agent makes the same call a thousand times and pays a thousand times

The second identical call should cost nothing. The thousandth should be served by something
small enough to run on a CPU. That is the entire product.

### What it does

**One connector, signed.** You call one API. It resolves to a verified source, fetches, and
returns a provenance envelope: which source, its licence, when the source recorded it, when
we fetched it, how stale that made it, a SHA-256 of the bytes, and a signature.

**A cache that learns.** Identical typed inputs return from an exact memo. Repeated question
shapes replay a cached path of small graded models instead of calling a frontier model. When
a path gets hot, it collapses into a single node trained on its own outputs. When a node is
near deterministic on a small input space, it becomes a lookup table.

**A grader you do not have to trust us about.** Every source, node and path has a public
scorecard computed by open code you can rerun against the same snapshot.

### The number

> Cost per answer fell more than fivefold between day one and day thirty, and the two
> cheapest tiers served over eighty percent of traffic by day thirty. Measured on a thirty
> day replay of two hundred requests a day against the example node.

That is a replay, not a production workload, and it is the honest state of the claim today.
The command that produces it is in the repository. The number we actually want is yours, from
your traffic, which is what the conversation below is for.

### What you get that you do not have now

| | Today, calling the API directly | Through the pipe |
|---|---|---|
| Repeat call | full price, every time | exact memo, then a distilled path |
| Provenance | the response body | source, licence, timestamps, staleness, hash, signature |
| "Where did this number come from?" | reconstruct it from logs | one receipt, traced across every hop |
| Historical replay | whatever you cached | `as_of` any past date, byte identical |
| Feed changed under you | you find out downstream | revision detection and a public scorecard |
| Out of scope question | a wrong answer | a refusal that names who to ask |

### What you give up

Nothing structural. We cache in front of the upstream rather than stand in front of it: on a
miss you get the upstream's own bytes with the upstream named, and you can check the hash
against the source. The schemas are Apache-2.0 and the archive is exportable, so the exit is
a file copy.

### What is not built yet

The fetch API is not public. Nodes talk over MCP and on one machine; the wire transport
between operators is next. Only some answer classes settle against an anchor, so accuracy
figures exist only where an anchor does. Cost per answer in production has not been measured,
because no production workload has been instrumented yet. Yours could be the first.

### The ask

One question, and a no is a useful answer:

> Given a measured cost cut and a signed envelope, would you replace one API call in your
> agent with one call to us?

If the answer is maybe, the next step is thirty minutes and a read-only look at one workload
to compute its repetition rate. If that rate is under twenty percent, we will tell you the
cache will not pay for itself and we will say so in writing.

[repository] · [quickstart] · [scorecards] · [the replay command]
