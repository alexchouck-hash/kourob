# Positioning: how to market Trooth, KouroB and Modafied

Derived from `docs/brief/06-kourob-trooth-modafied-plan.md`. Where this document and the
plan disagree, the plan wins. Dated 2026-09-14.

## The determination, in one paragraph

Market the measurement, sell the pipe, and never sell the grader. Modafied publishes free,
reproducible numbers about data sources people already depend on; those pages are the top of
the funnel and they carry no call to action. Trooth and KouroB sell one sentence to one
person: *your per-call cost falls as your volume rises, and every answer arrives with a
signature you can hand to an auditor.* Everything else in the material is proof of that
sentence. The emblems are the distribution mechanism and they compound at zero marginal cost.
Nothing is claimed that a reader cannot reproduce on their own machine.

## Why the obvious pitch is the wrong one

The tempting move is "AI agent data infrastructure." It fails four ways.

1. **The category is crowded and unfalsifiable.** Every entrant says the same words. A buyer
   cannot tell two of them apart without a trial, so nobody trials any of them.
2. **It attracts demo-watchers, not callers.** The Phase 1 gate is twenty five weekly active
   callers and one external developer who replaces a real call. Demos do not produce that.
3. **It puts Modafied inside the pitch.** The moment a Trooth price table mentions Modafied,
   the grader is a feature of a vendor and the independence is gone in appearance, which is
   the only place independence lives. M2 is not a compliance rule, it is the moat.
4. **It invites the comparison we lose.** Framed as infrastructure, the comparison is to
   funded platforms. Framed as a measurement, the comparison is to nothing, because nobody
   else publishes these numbers.

## Who we sell to, in the order the plan fixes

Section 6.4 fixes this order and says reversing it is how marketplaces die.

| # | Audience | What they want | What they get | Phase |
|---|---|---|---|---|
| 1 | **Agent developers making repeated structured calls** | cost per call to stop growing with volume | exact and class memo, a falling curve, a typed contract | 1 |
| 2 | **RA/QA, quant and compliance buyers** | to prove where a number came from | the envelope, the receipt chain, `as_of` replay | 1-2 |
| 3 | **Data providers** | distribution and a credential | catalog listing, a public scorecard, free revision tooling | 3 |
| 4 | **Node contributors** | a training loop they cannot afford alone | teacher labels, retraining, calibration, a scorecard | 4 |

Audience 1 is the only one being marketed to today. Audience 2 is reached by the same
material with a different opening paragraph. Audiences 3 and 4 are not addressed in public
until their gate is met, because a marketplace advertised before it works is a liability.

## The wedge: the benchmark is the marketing

Modafied answers questions people already type into a search box. How often does BLS revise
CPI. How stale is an NWS observation by the time you read it. Does openFDA change records
under you. Nobody publishes those answers, so the pages have no competition and a long
shelf life. They are also the cheapest marketing that exists: the scoring job runs anyway,
because the product needs the numbers.

Three rules keep the wedge sharp.

- **No call to action on a scorecard page.** The only ask is "run it yourself."
- **Every number links its reproduction command.** `make score --snapshot <id>` is the whole
  argument. A reader who runs it once will believe the next number without running it.
- **"Unmeasured" is a visible state.** A source with no scorecard looks different from a
  source with a bad one. That asymmetry is what makes providers come to us in Phase 3.

## The emblem loop: the one channel that compounds

An emblem is a small SVG with a grade, embedded by the graded party on their own site and
linked back to its scorecard. This is the mechanic behind build-status shields and security
audit badges, and it is already built and published.

```
Modafied grades a source  →  source embeds the emblem  →  their readers click through
        ↑                                                            ↓
   more sources ask to be graded  ←  the benchmark gets traffic and citations
```

It costs nothing per impression, it is durable, and it inverts the usual sales motion: the
graded party does the distributing. Three things make it work, and all three are cheap.

1. **One-line embed.** Markdown and HTML snippets on the emblems page, already there.
2. **An emblem worth showing.** A grade of B that is clearly mechanical is more flattering to
   a provider than a vague "trusted partner" badge, because readers know it was not bought.
3. **The notice travels with it.** "A measurement, not an endorsement" appears under every
   emblem. That sentence is why a good provider is willing to display a middling grade.

Do not put a price on an emblem, ever, in any form, including a "featured" slot. The first
paid placement converts the whole channel into advertising and it never converts back.

## Message architecture: three properties, three jobs

| Property | Job | One line | Sells |
|---|---|---|---|
| **Modafied** | earn trust, generate inbound | "Open, reproducible measurements of how data sources actually behave." | nothing, by rule |
| **Trooth** | convert the developer | "One connector for external data. Every answer signed, dated, and traceable." | the pipe, metered |
| **KouroB** | keep the developer | "Answers that get cheaper the more you ask for them." | the margin |

They are marketed as related but not bundled. The honest phrasing of the relationship, which
belongs on the Modafied conflict policy page and nowhere else: *Modafied's public scorecard
compute is funded by Trooth under a fixed published transfer that does not vary with any
score. Trooth's own sources and servers are graded by the same code as everyone else's.*

## The proof stack, in order of persuasive power

1. **The cost curve.** One number, measured, with the command beside it. Today the honest
   version is a thirty day synthetic replay on the example node, and the copy says so.
2. **The chain.** A trace crossing three nodes with price and cost per hop. Nobody else can
   show this, because nobody else receipts refusals.
3. **The refusal.** A node that answers "not mine, ask them" and hands back a route is more
   trustworthy than one that guesses. Show a refusal in the demo on purpose.
4. **The open grader.** "You do not have to trust our numbers" closes the loop, and it is the
   only one of the four a competitor cannot copy without giving up their own revenue.

## Against the alternatives, honestly

| The reader is doing | What we say |
|---|---|
| Calling the upstream API directly | Keep doing it. We cache in front of it rather than stand in front of it: on a miss you get the upstream's own bytes, hashed, with the upstream named, and you can check the hash yourself. What you gain is provenance you did not have and a cost curve that bends down. |
| Using an API aggregator | They sell access. The access is not the hard part. Nobody there can tell you how often that feed revised last month, and nobody hands you a signature. |
| Building their own cache | Reasonable, and most teams should. Yours will not have revision detection, a public grade, or an envelope you can give a regulator. Ours is also open enough to leave with. |
| Having a frontier model do it | We are not competing with it. It is our teacher, our planner and our miss handler. It just never sits in the hot path, because paying frontier prices for the same lookup a thousand times is the waste we exist to remove. |
| Waiting for someone bigger to ship this | The compounding asset is the snapshot archive and the graded trace corpus. Neither can be backfilled by someone who starts later. That is the whole reason to start now and say so. |

## What may never be claimed

This list is enforceable. A piece of copy that breaks one of these does not ship.

- **Never** put Modafied in a Trooth or KouroB price table, feature list, or sales deck as a
  capability of the product. Reference it the way you would reference an outside auditor.
- **Never** write *verified*, *certified*, *endorsed*, *approved*, *partner*, or *trusted*
  next to an emblem or a scorecard. The word is *measured*.
- **Never** state a synthetic measurement as a production one. "On a thirty day replay of the
  example node" is four extra words and it is the difference between credible and not.
- **Never** describe the fetch API as available while `/fetch` is not public.
- **Never** use *decentralized*, *trustless*, *token*, *chain*, *emissions*, or *community
  governed*. The plan rejects all of them and the target buyer reads them as a warning.
- **Never** publish a number without the command that reproduces it.
- **Never** remove the "what is not built yet" section from a page to make it read better.

That last one is a weapon, not a tax. A technical reader has been lied to by every landing
page they have ever read. A page that volunteers its own gaps is so unusual that it reads as
proof of the rest, and it costs nothing because the gaps are in the repos anyway.

## Names: the honest read

Section 13 item 1 asks for this, and marketing is the right lens for it.

- **Trooth.** The name promises truth. The product carefully does not claim truth; it claims
  provenance, which is a different and more defensible thing. Every piece of copy will spend
  a sentence walking the name back. That is a permanent tax on every page, and the
  misspelling also costs search traffic to the correctly spelled word. Worth changing while
  changing it is still cheap.
- **Modafied.** Reads as "modified", which suggests alteration. For a grader whose entire
  value is that it changes nothing and only measures, the name says the opposite of the
  product. It is also close enough to a well known drug name to be a search and trademark
  hazard. This is the one I would change first.
- **KouroB.** Opaque, and opacity is fine for infrastructure that developers reach through a
  client library. Keep it. Note that it is the only one of the three that never has to appear
  in a non-technical conversation.

## How marketing is measured

Not impressions. The plan's own commercial and desirability gates are the targets, so every
channel is judged on whether it produces a specific gate event.

| Gate | The event marketing must produce |
|---|---|
| Phase 0 | one outside reader asks us to add a source |
| Phase 0b | one RA/QA reader uses a node scorecard unprompted |
| Phase 1 | twenty five weekly active callers; one external developer replaces a direct call and says why |
| Phase 2 | one paying customer, who then renews or expands |
| Phase 3 | three providers listed, one paid feed transacting, one provider citing their scorecard in public |

If a channel has not produced its gate event, it is not working, whatever its traffic says.
