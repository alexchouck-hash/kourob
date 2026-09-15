# Draft: the Phase 0 launch post

Status: draft, not sent. Gate: Phase 0. Ask of the reader: which source to measure next.

**Before sending, check three things.** The conflict policy page is live. Every number below
matches the current published scorecard. The sample counts quoted are the real ones.

---

## Title options

1. **We measured five public data feeds on six dimensions. The code is open and the numbers
   reproduce byte for byte.**
2. Show HN: an open benchmark for public data feeds, with reproducible scorecards
3. How stale, how revised, how consistent: measuring five public feeds

Use 1 on Hacker News. It is a measurement, not a launch, and the title should say so.

---

## Body

Every agent and every app that pulls public data makes the same three assumptions: the feed
is current, it will not change under you, and the fields you need are populated. Almost
nobody checks. We started checking, and we published the checker.

Modafied snapshots public feeds on a schedule, keeps every snapshot, diffs them, and computes
a scorecard on six dimensions:

- **freshness lag**: how old the data already is when you receive it
- **revision behavior**: how often published records change afterward
- **correction latency**: how long a correction takes to appear
- **completeness by segment**: how many declared fields actually arrive populated
- **schema stability**: how often the shape changes
- **internal consistency**: how often a snapshot contradicts itself

Accuracy is a seventh number and it only appears when there is a named anchor to grade
against, because an accuracy figure with nothing behind it is a decoration.

The first five sources are the National Weather Service, Open-Meteo, the USGS earthquake
feed, the Bureau of Labor Statistics, and FRED.

### What we found so far, and how thin it is

The honest headline is that the interesting result is a method, not yet a verdict. The
scoring window is short and the sample counts are small, and the scorecards say so on their
face: two of the five sources currently read **insufficient data** rather than showing a
grade, because too few of the six dimensions were measurable. That state is deliberate. A
benchmark that produces a number no matter what is a benchmark that produces a wrong number.

What the early numbers do suggest, and what we would like people to attack:

- The authoritative source is not automatically the best behaved one. On the current window,
  the primary weather source grades below the derivative that republishes it, mostly on
  revision behavior and correction latency. That may be a real property of official
  observations being corrected after the fact, or it may be an artifact of a short window.
  We would like to know which.
- Revision behavior is the dimension nobody instruments and the one most likely to break a
  downstream pipeline quietly.
- Being measurable at all is a differentiator. Some feeds simply do not expose enough for
  four of the six dimensions to be computed.

### The part that matters: you can rerun it

```
make score --snapshot <id>
```

Same snapshot, same bytes, on your machine. If your output differs from ours, that is a bug
report and we want it. The scoring code, the method, the anchor registry and the schemas are
Apache-2.0.

We are also writing up how to run a full independent replica, which snapshots the same
sources and publishes a signed hash. Two replicas either agree or they do not. That is the
only trust mechanism here: no votes, no tokens, no honest majority assumption.

### Who pays for this, before you ask

The public scorecard compute is funded by a fixed, published transfer from a commercial
sibling project that resells access to some of these same feeds. That is a conflict, and the
answers to it are structural rather than promised: the grader is a separate repository with
its own conflict policy, it takes no money from any party it grades, the transfer does not
vary with any score, and the sibling's own sources are graded by the same code and published
whatever they say. If we ever cannot keep that true, we stop publishing scores for sources
that project resells, and the method page will say so.

### What we want

Tell us which source to measure next, and tell us if a number looks wrong. A dispute needs a
reproduction, and every dispute is public.

[link to the method page] · [link to the scorecards] · [link to the repository]

---

## Comment replies to have ready

**"Your sample size is tiny."** Correct, and the scorecards show the count on every
dimension. That is why two of five read insufficient data instead of showing a grade. The
window grows daily and the archive is the point: nobody who starts later can backfill it.

**"This is marketing for your paid product."** The grader takes no revenue from anything it
grades and has no call to action on any scorecard page. The funding arrangement is on the
conflict page with a number on it. Grade our own feeds harder than anyone else's and we will
consider that a fair complaint.

**"Six dimensions is arbitrary."** It is a choice, documented with a version and a changelog,
and it is designed so that gaming one degrades another: publish early to win freshness and
your revision rate climbs; suppress corrections to protect revision rate and internal
consistency drops. Propose a seventh with an ADR.

**"Why not just use the source's own SLA?"** Because an SLA is a promise and this is a
measurement, and the interesting cases are exactly where they differ.
