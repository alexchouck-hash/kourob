# Launch sequence: what ships when, and which channel produces which gate

Every item here is tied to a phase gate in plan section 10. Nothing from a later phase is
marketed early, for the same reason nothing from a later phase is built early: a claim that
outruns its gate is a claim a reader can falsify.

## Phase 0, now: the benchmark is the launch

**What is true today and therefore claimable:** five public sources scored on six
dimensions, a versioned method, emblems published, and every number reproducible from a
named snapshot. The fetch API is not public and no copy says otherwise.

| # | Piece | Where | Ask of the reader |
|---|---|---|---|
| 1 | Scorecards for the five sources | Modafied site | none |
| 2 | Method page with the reproduction command | Modafied site | "run it" |
| 3 | The conflict policy page, including the fixed transfer | Modafied site | none |
| 4 | Emblems page with the one-line embed | Modafied site | "embed yours" |
| 5 | Launch post: *we measured five public feeds* | HN, Lobsters, the communities around each source | "which source next?" |

**Gate event to produce:** one outside reader asks for a source to be added. That single
reply is the Phase 0 desirability gate, and it is a better signal than a thousand upvotes.

**Where to post, in the order they are worth doing.** The communities around each graded
source matter more than the general ones, because the reader there already knows the feed
and will argue with the number, which is the engagement that proves the method.

1. The specific communities: weather API developers, r/econmonitor and FRED users, the
   openFDA and RA/QA forums, r/dataengineering.
2. Hacker News, titled as a measurement and not as a launch. The reproducible build angle is
   the part that survives the front page.
3. Lobsters, which rewards the same thing and has a better signal to noise on method.

**Conflict policy page ships before any scorecard is public under the Modafied name.** This
is M-07 in the queue and it is a marketing dependency, not just a governance one: the first
sophisticated reader will look for who pays, and finding the answer already published is
worth more than any other sentence on the site.

## Phase 0b: the first node's scorecard is the second post

The `maude.dedup` node moving SEEDED to SHADOW to SERVING is the first evidence that the
grading method works on models and not just on feeds.

- **Post:** *a deduplication model, graded in public* with precision, recall, the anchor it
  was graded against, and the gold set version.
- **Channel:** RA/QA communities, where MAUDE deduplication is a known chore.
- **Gate event:** an RA/QA reader uses the node scorecard unprompted.

Do not market this as "our AI." Market it as a measured component with a published error
rate, which is what the audience has never been offered before.

## Phase 1: the cost curve, and the first direct selling

This is where Trooth and KouroB become sellable, because there is finally a number.

| # | Piece | Purpose |
|---|---|---|
| 1 | Developer one-pager (`drafts/developer-one-pager.md`) | the link sent to a named developer |
| 2 | Post: *our cost per answer fell over thirty days, here is the replay* | inbound for audience 1 |
| 3 | A worked trace: one answer, three nodes, price and cost per hop | the provenance proof |
| 4 | Quickstart that reaches a cited answer in under ten minutes | conversion |
| 5 | Ten direct outreach conversations (`drafts/outreach.md`) | the gate, directly |

**The number, stated honestly.** Today it is: cost per answer fell more than fivefold between
day one and day thirty, and cheap tiers served at least eighty percent of traffic by day
thirty, on a thirty day replay of two hundred requests a day against the example node. When
a production workload is instrumented, restate it with that workload named. Do not drop the
qualifier to make the sentence shorter.

**The ten conversations are the real Phase 1 marketing.** The desirability test is a sentence
with a yes or no answer: will this developer replace one API call with one call to us, given
a measured cost cut and a signed envelope. Ask exactly that, to ten people, and write down
the ten answers. A "no, because" from a real developer is worth more than the post.

**Gate events:** twenty five weekly active callers, one of them a 10xAnd tool; one external
developer who replaces a direct call and says why.

## Phase 2: replicas and the first paying customer

- **Post:** *two hosts, same snapshot, same hash.* Replication is the most defensible claim in
  the whole system and almost nobody in the data space can make it. Lead with the hash.
- **Invite replicas** in the same post, with the runbook linked. Target three, one not
  operated by Alex.
- **Case note** with the first paying customer, if they allow it: the workload, the
  repetition rate, the measured cut. One page, numbers only.
- **Gate event:** the first customer renews or expands.

## Phase 3: providers, and the message inverts

Until now the material has addressed buyers. Here it addresses supply, and the pitch is
distribution and credential before money, in that order, because that is the order the plan
says actually pulls.

- **Provider page:** what listing gets you, in the order of section 6.2. Being routable.
  The scorecard as public proof. Metered payouts at a published take rate. Free revision and
  schema-change monitoring on your own feed, which most providers have never seen.
- **The opener that works:** send a provider their own measurement before asking for
  anything. "We measured your feed. Here is what we found. You can embed it." Most providers
  do not know their own revision behavior and will reply to that email.
- **Gate event:** a provider cites their scorecard publicly.

## Phase 4: contributors

Invited only, in verifiable classes. The pitch is the training loop, not the revenue share:
list your node and the network labels its low confidence traffic, retrains it, recalibrates
it, and grades it in public, none of which a solo builder can afford.

No public campaign for this phase. The first contributors are people already in the
conversation.

## The standing rhythm, once Phase 1 is live

Small and regular beats large and occasional, and all of it is a byproduct of work that
happens anyway.

| Cadence | Piece | Source |
|---|---|---|
| Per scoring run | scorecards update themselves | the jobs |
| Monthly | *what changed in the feeds we watch*: revisions, schema changes, corrections | the diff archive |
| Per node reaching SERVING | its scorecard, announced once | the lifecycle |
| Per collapse | the before and after cost, with the path | the trainer |
| Quarterly | method changelog and gold rotation note | the ADRs |

The monthly revision note is the sleeper. It is the only recurring content in this space that
is genuinely useful to people who will never buy anything, and it is generated from data the
system already keeps.

## What not to do, with reasons

- **No launch video, no animated diagram, no product hunt.** The audience discounts them.
- **No "request a demo" gate.** The free tier requires no account by rule; a demo gate on top
  of a no-account product is incoherent.
- **No paid acquisition before Phase 2.** With no paying customer there is no number to
  compute a payback against, so spend is guessing.
- **No conference booth before Phase 3.** Booths sell to supply, and supply is not the
  audience until then.
- **No comparison table against named competitors.** The honest comparison is against what
  the reader is doing today, which is calling the API directly. Naming competitors invites
  their rebuttal and gives them the traffic.
