# The copy bank

Approved lines, the objections they answer, and the claims that may never ship. House style
follows the Trooth site rules: plain copy, no hype, no em dashes, no claim without a
scorecard or a reproduction command behind it.

## One-liners

| Use | Line |
|---|---|
| Trooth, primary | One connector for external data. Every answer signed, dated, and traceable to its source. |
| Trooth, short | One connector. Every answer signed. |
| KouroB, primary | Answers that get cheaper the more you ask for them. |
| KouroB, technical | Small graded models replay the answers a frontier model used to compute. |
| Modafied, primary | Open, reproducible measurements of how data sources actually behave. |
| Modafied, short | Measured, not endorsed. |
| The three together | Trooth is the pipe. KouroB is the cache that learns. Modafied is the grader, and it is nobody's product. |

## The elevator, thirty seconds

> If your agent calls the same external API thousands of times, you pay full price every time
> and you cannot prove where any answer came from. Trooth wraps every fetch in a signed
> envelope with the source, the timestamp and a hash. KouroB remembers the answers and learns
> to produce the repeated ones without the expensive call, so cost per answer falls as volume
> rises instead of climbing with it. Modafied grades the sources and the models in public,
> with code anyone can rerun, so you do not have to take our numbers on faith.

## The claim, and how to state it honestly

**Today, the only honest form:**

> Cost per answer fell more than fivefold between day one and day thirty, and the two
> cheapest tiers served over eighty percent of traffic by day thirty, on a thirty day replay
> of two hundred requests a day against the example node. The command that produces those
> numbers is in the README.

**When a production workload is instrumented,** restate it naming that workload and its
repetition rate. Never drop "on a replay" to shorten the sentence. Four words are the
difference between a claim a reader can check and one they cannot.

**The number the whole thesis rests on** is the repetition rate of the first instrumented
workload. Under twenty percent, the cache thesis is wrong and the marketing changes with it.
Do not build a campaign that cannot survive that finding.

## Openings by audience

**Agent developer.** "Your agent makes the same structured call a thousand times a day and
pays a thousand times. The second identical call should be free, and the thousandth should
be served by something small enough to run on a CPU. That is the whole product."

**RA/QA, compliance, quant.** "When someone asks where this number came from, you need an
answer that holds up: which source, at what time, how stale it was, and a hash that proves it
has not changed since. Every response carries that, and you can replay any query as of any
past date."

**Provider, Phase 3.** "We measured your feed on six dimensions. Here is what we found. Most
providers have never seen their own revision behavior. You can embed the result or ignore it,
and either way we will keep measuring."

**Contributor, Phase 4.** "List a node and the network trains it for you: teacher labels on
its low confidence traffic, retraining on a cadence, calibration, and a public scorecard. No
solo builder can afford that loop."

## Objections, with the answers that are true

**"This is another middleman between me and my data."**
We cache in front of the upstream rather than stand in front of it. On a miss you get the
upstream's own bytes, hashed, with the upstream named and its licence attached, and you can
verify the hash against the source yourself. On a hit you get the same bytes you got before,
with the timestamp of when they were fetched.

**"Why would I trust your benchmark?"**
Do not. The scoring code, the method and the anchors are Apache-2.0, and `make score
--snapshot <id>` reproduces every published number byte for byte on your machine. If you run
a replica we will list your attestation next to ours, and if our hashes differ that is a bug
report, not a debate.

**"What happens to my data if you disappear?"**
Envelopes and receipts are files, the schemas are open, and the snapshot archive is
exportable. There is nothing to be locked into except the archive itself, and that is the
part you would want to keep.

**"Is this a blockchain thing?"**
No. No token, no chain, no consensus mechanism, no emissions. Credits are an internal ledger
and no money moves in v1. Independent replicas agreeing on a hash is the only decentralization
here, and it needs no honest majority assumption.

**"Distilled models are worse than the frontier model."**
Often, yes, which is why every node publishes its accuracy against a named anchor and refuses
below its threshold instead of guessing. A node that is not good enough at a class does not
serve that class. The frontier model handles the miss.

**"Our data is private."**
Nothing private is ever graded in public. Private sources and private nodes can be graded as
a service, for you, and those scorecards are yours.

**"You are grading sources you also resell. That is a conflict."**
It would be, which is why the grader is a separate repository with a published conflict
policy, takes no revenue from any party it grades, is funded for public scorecard compute by
a fixed published transfer that does not vary with any score, and grades our own sources and
servers with the same code as everyone else's. If we cannot keep that true we stop publishing
scores for sources we resell and say so on the method page.

## Words we use, and the words they replace

| Say | Not |
|---|---|
| measured | verified, certified, validated |
| a measurement | an endorsement, a seal, a badge of trust |
| provenance | truth, ground truth, guaranteed accuracy |
| cheaper per answer as volume rises | infinitely scalable, near zero cost |
| a node refuses and refers | the AI decides, intelligent routing |
| distilled model, graded against an anchor | proprietary AI, our model |
| open and reproducible | transparent, trustless |
| not built yet | coming soon, on the roadmap |

## Forbidden claims

A draft containing any of these does not ship, regardless of who wrote it.

1. Modafied named as a Trooth or KouroB feature, in a price table, or in a sales deck.
2. *Verified*, *certified*, *endorsed*, *approved*, *partner* or *trusted* beside an emblem.
3. A synthetic or replayed measurement presented as production.
4. The fetch API described as available while it is not public.
5. *Decentralized*, *trustless*, *token*, *chain*, *emissions*, *community governed*.
6. Any accuracy figure without a named anchor beside it.
7. Any number without its reproduction command.
8. A paid placement, featured slot, or sponsored grade of any kind.
9. A customer named without their written permission.
10. A page with the "what is not built yet" section removed.

## Boilerplate

**Modafied, under any emblem, verbatim:**

> Mechanically computed from public snapshots. This is a measurement, not an endorsement, a
> verification, or a partnership. It cannot be purchased and it changes without notice when
> the measurement changes.

**Trooth, in a footer:**

> Trooth resolves requests to verified sources, fetches, and wraps every response in a
> provenance envelope: source identity, licence, timestamps, freshness lag, a SHA-256 hash and
> a signature. The fetch API is not public yet.

**KouroB, in a footer:**

> KouroB is an open structure for building nodes: small, metered, provenance-tracked units of
> knowledge that agents attach to. Apache-2.0.

**The relationship, when it must be stated, and only on Modafied's conflict page:**

> Modafied's public scorecard compute is funded by Trooth under a fixed published transfer
> that does not vary with any score. Trooth's own sources and servers are graded by the same
> code as everyone else's, and their grades are published whatever they say.
