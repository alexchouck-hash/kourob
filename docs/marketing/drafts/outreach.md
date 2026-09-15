# Draft: outreach

Status: drafts. Three templates and the script for the ten Phase 1 conversations. All short
on purpose. None of them asks for a call before giving something.

---

## 1. The ten developers, Phase 1 desirability gate

Pick ten people whose agent or app makes repeated structured calls to public data. Send this,
then run the script below on whoever replies. Record all ten answers, including the silences.

**Subject:** the repetition rate of your API calls

> Hi <name>,
>
> You mentioned <specific thing they built> calls <source> on a loop. I am working on
> something narrow: a connector that returns every fetch inside a signed provenance envelope,
> and a cache in front of it that learns to answer the repeated shapes with small graded
> models instead of a frontier call.
>
> On a thirty day replay of our example node, cost per answer fell more than fivefold by day
> thirty. That is a replay, not production, which is why I am writing to you rather than
> announcing anything.
>
> One question, and no is a genuinely useful answer to me: given a measured cost cut and a
> signed envelope, would you replace one API call in <their thing> with one call to us?
>
> If it is a maybe, I would like thirty minutes and a read-only look at one workload to
> compute its repetition rate. If that rate comes back under twenty percent I will tell you
> the cache will not pay for itself, in writing, and we can both stop.
>
> <one-pager link>
>
> Alex

**The script, once they reply.** Five questions, in this order, and write down the words they
use rather than summarising them.

1. Which call do you make most often, and roughly how many times a day?
2. How often is the input identical to one you sent before?
3. When something downstream is wrong, how do you find out which fetch caused it?
4. Has a feed ever changed shape or revised a value under you? What happened?
5. What would have to be true for you to route one call through someone else?

Question 2 is the viability test. Question 4 is where the envelope sells itself. Question 5
is the only one whose answer belongs in the product plan.

**What counts as the gate:** one of the ten replaces a direct call and can say why in their
own words. Not a trial, not an integration promise. A replaced call.

---

## 2. Providers, Phase 3

Never ask first. Measure, then send the measurement, then ask nothing.

**Subject:** we measured <feed> and thought you should see it

> Hi <name>,
>
> We run an open benchmark of public data feeds and <feed> is in it. Your scorecard is here:
> <link>. Six dimensions, all mechanical, code is open, and the command that reproduces every
> number is on the method page.
>
> Two things you may not have seen about your own feed: <specific finding, one sentence> and
> <second finding>. Most providers have never had their revision behavior measured, including
> the ones who are good at it.
>
> Nothing is being asked of you. If the number looks wrong, file a dispute with a
> reproduction and we will publish the resolution either way. If it looks right and you want
> to show it, the embed is one line: <emblem snippet>.
>
> Alex

**Only after they engage,** and only if they ask what else exists, mention listing: being
routable to every agent on the pipe, metered payouts at a published take rate, and free
revision and schema-change monitoring on their own feed. Distribution and the credential come
before money in that conversation, because the plan says those are what actually pull.

---

## 3. Replica operators, Phase 2

**Subject:** run a replica and we will publish your hash next to ours

> Hi <name>,
>
> We publish scorecards for public data feeds and claim they are reproducible. That claim is
> worth nothing while we are the only ones computing them.
>
> The runbook for an independent replica is here: <link>. It snapshots the same sources,
> computes the same scorecards, and publishes a signed hash. Two replicas either produce the
> same hash from the same snapshot or they do not, and a disagreement is a bug report rather
> than an argument.
>
> We will list your attestation alongside ours, including the runs where we disagree. We are
> looking for three replicas and at least one that we do not operate.
>
> Alex

Good targets: university data groups, civic tech organisations, an existing replica-shaped
project in an adjacent space, and the operators of any source who want to check our work on
themselves.

---

## Rules for all outreach

- Give a measurement before asking for anything.
- Never send to a list. Every one of these is written to a named person about a specific thing
  they built.
- No follow-up sequence. One follow-up after ten days, then stop.
- A no gets a thank you and the reason recorded, never a rebuttal.
- Never send a claim that is not in `MESSAGES.md`.
