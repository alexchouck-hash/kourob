# Draft: 10xAnd case study, counting distinct events in MAUDE

Status: draft, 2026-09-14. Property: 10xAnd.com. Proposed route: `/maude/method/distinct-events/`.
Source material: `CLAUDE_CODE_SPEC_MAUDEScope_v0_1.md` sections 4, 5.1 to 5.2, 5.9 to 5.11, 8, 9;
`EXAMPLE-01-maude-distinct-events.md`; `06-kourob-trooth-modafied-plan.md` section 10 (phase 0b gates).

---

## Read this before editing a word of the copy

The 10xAnd Phase 1 spec bans three things this document had to be written around, and the
constraints are why it reads the way it does.

| Constraint | Where | What it rules out |
|---|---|---|
| No invented track record | Phase 1 §1.3 | a client story, a testimonial, an operating history, any benchmark number that is not defensible |
| No client names, ever | Phase 1 §1.2 | naming who the work was for, including obliquely |
| No case studies | Phase 2 §13 | a `/case-studies/` section, a CMS, a portfolio |

So this is not a client case study. It is a **method case study on public data**: one question,
the method that answers it, the validation that says whether the method works, the review record
that makes the output usable, and the sentence the output may never be used to say. It carries no
client, no engagement history, and no measured result that has not been produced yet.

Phase 1 §1.3 permits four kinds of number on a page: a credential, a standard's requirement, a
publicly verifiable fact, or an explicit design target labelled as such. **Every number below is
one of those four and section 11 says which.** Any number that is not yet measured appears as a
`{{PLACEHOLDER}}` or as a labelled target, never as a result.

**Where it lives.** Not under a new `/case-studies/` route, which Phase 2 §13 closes. It belongs
under `/maude/method/` as a child page, because MAUDEScope §7 already names the method page the
credibility asset, and because a reader who arrives here is one click from the scorecard the page
describes. Link it from `/remediate` in the post-market FAQ fold (Phase 2 G6) and from `/pulse`,
and nowhere else.

---

## The page copy

### Document control block

Rendered in the site's spec-block component, monospace, document-control border.

```
10X-CS-001                                                            REV A
─────────────────────────────────────────────────────────────────────────────
SUBJECT      Estimating distinct events from MAUDE report counts
DATA         openFDA device/event, public, snapshot {{SNAPSHOT_ID}}
METHOD       maudescope dedup v0.1
VALIDATION   {{GOLD_PAIRS_N}} hand-labelled pairs per product code
CLAIMS       counts and estimates only; no rate, no ranking, no causation
STATUS       method published; validation figures pending first labelling round
```

### Headline

**A MAUDE report count is not an event count, and the gap is not small.**

### Subhead

One product code, one public dataset, and the method that turns reports into an estimate of
distinct events, with its error rate published beside it.

---

### 1. The question

An RA/QA lead asks a question that sounds like it has a lookup answer:

> How many adverse events were reported for this product code in the last twelve months?

The FDA's public MAUDE search returns a number in a second. That number is the count of **reports**
on file. It is not the count of **events**, and the two differ for reasons that have nothing to do
with the device.

- A single event can generate a manufacturer report, a user facility report, and a voluntary
  report, filed separately by three parties who never spoke to each other.
- Follow-up submissions to an earlier report are separate records.
- Identifiers are dirty enough that the same device appears under several spellings of its brand
  name, so naive grouping does not collapse them.

Count reports and call them events and every downstream number moves: the trend, the quarter over
quarter comparison, the figure that goes into a complaint trend report or a CAPA input. The error
is systematic, not random, and it does not average out.

### 2. Why nobody publishes the corrected number

Because correcting it requires a method, a method requires a validation set, and a validation set
requires somebody to hand-label pairs of reports as the same event or not. That is unglamorous
work, it has to be redone when the method changes, and there is no published place to put the
result. So the raw number stays in circulation.

Three structural facts about MAUDE compound the problem, and all three are public and stated by
the FDA itself. They constrain what any method here can honestly claim.

1. **There is no denominator.** MAUDE contains counts, not rates. Nothing about how many devices
   are in use is in the file, so no count in it can be turned into a rate.
2. **A report is not a finding.** The FDA does not verify reports, and a report does not establish
   that a device caused the event described.
3. **Some counts sit on either side of a programme boundary.** The FDA has run summary reporting
   programmes under which certain events were reported in aggregate rather than as individual
   public MDRs. Where a product code is affected, counts are not comparable across that boundary
   and the page says so instead of silently joining the series.

A method that ignores any of the three produces a number that a notified body or an investigator
will take apart. This one states all three on the face of the output.

### 3. The method, published verbatim

Two passes, both deterministic, both versioned. The goal is an estimate of distinct real-world
events, not perfect record linkage, and the method says so.

**Pass 1, exact linkage.** Group records that share an event key where one is present. Group
follow-up submissions to their initial submission through the shared report number root.

**Pass 2, fuzzy linkage.** Within a single product code, two records are a candidate pair when all
of the following hold:

- the normalised manufacturer name matches, and
- the date of event is within plus or minus 3 days, and
- the event type matches, and
- at least one of the normalised brand name, the lot number, or the model number matches.

A candidate pair is confirmed when the two records share an identical product problem set, or when
their event descriptions reach a MinHash Jaccard similarity of 0.6 or above.

Confirmed pairs are resolved into clusters with union-find. One cluster is one estimated event.

```
raw_reports       records carrying the product code
dedup_events      clusters after both passes
duplicate_rate    1 - (dedup_events / raw_reports)
```

Every figure published from this method carries its `method_version`. The method is never changed
quietly: a change bumps the version, the prior version's outputs are kept, and the change is
written into the amendments log on the method page.

### 4. A worked example

Illustrative only. The numbers below are placeholders until the first validated run publishes;
the shape of the answer is the point.

```
PRODUCT CODE      {{EXAMPLE_CODE}}  ({{EXAMPLE_DEVICE_NAME}}, Class {{EXAMPLE_CLASS}})
WINDOW            trailing 12 months, snapshot {{SNAPSHOT_ID}}

raw_reports                    {{RAW_12M}}
dedup_events        estimated  {{DEDUP_12M}}
duplicate_rate      estimated  {{DUP_RATE}}   CI {{DUP_RATE_CI}}
method_version                 0.1
```

What changes when the second number replaces the first: the quarterly trend flattens or steepens,
a quarter that looked like a spike may turn out to be one event reported by four parties, and a
quarter that looked flat may turn out to contain more distinct events than the one beside it. The
scorecard shows both series on the same axes for exactly this reason. Neither number is hidden.

### 5. How we know whether the method works

This is the part that decides whether the number is usable, and it is the part usually left out.

**The validation set.** A sample of candidate pairs per product code, labelled by hand as duplicate,
not duplicate, or unsure. Where more than one person labels, inter-annotator agreement is measured
and published alongside the result. The labelled set is held out: the clustering code never reads
it, and the build fails if it does.

**The figures published.** Precision and recall of the method against that labelled set, with the
version of the labelled set named. They appear on the method page whether they are flattering or
not, because a method with an unpublished error rate is an opinion.

**The floor, enforced by the build.** Design targets, stated as targets:

| Measure | Target | Status |
|---|---|---|
| Precision against the labelled set | 0.85 or above | design target, not yet measured |
| Recall against the labelled set | 0.70 or above | design target, not yet measured |
| Scope expansion beyond the starting product codes | precision 0.85 or above first | design target |

The publishing pipeline refuses to deploy a scorecard whose precision is below the published floor.
That is a build step, not a promise.

**What happens until then.** Until a real labelled set exists, the pipeline runs against a fixture
set that is marked synthetic in its own header, and the scorecard generator refuses to publish a
card built from it. It writes the card to a fixtures directory instead. The result is that the site
can be built and tested end to end without a single number reaching a page that has not been
validated. Nothing is published early to make the page look finished.

### 6. The review record

A duplicate rate that ends up in a post-market surveillance file needs to carry who stood behind it.
The cleaned export does, without an account and without sending anything anywhere:

1. The reviewer enters their name and organisation. Both stay in the browser.
2. The reviewer dispositions three method statements, the deduplication method, the lag exclusions,
   and the spike threshold, as accepted, accepted with note, or rejected.
3. The exported file's header rows record the reviewer name, the dispositions, the method version,
   the source snapshot, and the timestamp.

The file arrives already carrying its own review record. A named human has dispositioned the method
before the data leaves the browser, which is the same pattern as a named reviewer on an AI-assisted
deliverable, applied to a free tool.

The share image is free and ungated, because an illustration is not a deliverable. The cleaned
slice is gated behind the disposition, because it is.

### 7. What this may never be used to say

Fixed text, rendered from the scorecard's own disclaimer list, never paraphrased.

- **No rate.** MAUDE contains counts, not rates. Differences between product codes reflect market
  size, reporting practices, and reporting requirements as much as anything about a device.
- **No causation.** An MDR is a report, not a finding. The FDA does not verify reports, and a report
  does not establish that a device caused the event described.
- **An estimate.** Distinct event counts and duplicate rates are estimates produced by a published
  method with a published error rate.
- **No ranking.** This method never says one device or one manufacturer is safer than another, and
  the comparison surface never uses the words better or worse.

At version 0.1 the output is product code level only. Manufacturer and brand breakdowns are held
until the nominative use question is settled, and the output format is designed so that adding them
later does not break the schema.

### 8. What is not built yet

Stated here because leaving it out is the thing that would make the rest less believable.

- The hand-labelled validation set does not exist yet, so precision and recall are targets, not
  results. Section 5 says which.
- Revision behaviour, meaning how often records change under you after publication, needs several
  weekly snapshots before it can report anything. Until then it reports insufficient history and
  names the number of snapshots it has.
- Coverage starts at a small allowlist of product codes, not the whole database.
- Spike annotation matches recalls only. A spike with no recall match is shown as unannotated
  rather than explained.

### 9. Where the tool stops and the work starts

The tool finds the question. It will tell you that a product code has an estimated duplicate rate
of {{DUP_RATE}} and a quarter that sits above its own baseline. That is a finding, and it is free.

It does not produce the post-market surveillance analysis, the complaint trend report, or the CAPA
input that a notified body or an FDA investigator will accept. That is the engagement: the same
method, your own data alongside the public data, and a named human reviewer on every document.

**If this is your product code**, the pilot is below.

### 10. Pilot block

Rendered in the shared spec-block component, matching the other service pages.

```
10X-SVC-PMS                                                           REV A
─────────────────────────────────────────────────────────────────────────────
OFFER        Post-market signal review, one product code
SCOPE        {{PMS_SCOPE}}
PRICE        {{PRICE_BAND_PMS}}
LEAD TIME    {{LEAD_TIME_PMS}}
SLOTS        3 founding clients
```

Primary call to action: the email capture, with `source_page` set to the post-market key,
`vertical_hint` unset, `persona_hint` set to the RA/QA and R&D value. Secondary: the booking
popup with UTM passthrough. Both identical to every other page, so the comparison between
pitches stays a comparison of message.

---

## 11. Claims register

Every number that appears in the copy, its permitted type under Phase 1 §1.3, and who owns it.
A reviewer works this table, not the prose.

| # | Number in copy | Type under §1.3 | Owner | Note |
|---|---|---|---|---|
| 1 | plus or minus 3 days, date of event window | published method parameter | method | on the method page verbatim |
| 2 | Jaccard 0.6 narrative similarity threshold | published method parameter | method | same |
| 3 | 8 quarter rolling median, 3 x MAD, 20 event floor, spike rule | published method parameter | method | referenced, not restated in the hero |
| 4 | precision 0.85 or above | **explicit design target, labelled** | founder | must never render without the label |
| 5 | recall 0.70 or above | **explicit design target, labelled** | founder | same |
| 6 | 4 snapshots before revision metrics report | published method parameter | method | |
| 7 | MAUDE has no denominator | publicly verifiable fact | FDA | cite the FDA MAUDE disclaimer page |
| 8 | the FDA does not verify reports | publicly verifiable fact | FDA | same citation |
| 9 | summary reporting programmes affect comparability | publicly verifiable fact | FDA | needs the release URL, see TODO |
| 10 | 3 founding client slots | offer term | founder | matches every other spec block |
| 11 | every `{{PLACEHOLDER}}` in section 4 and 10 | **not yet a number** | founder | page does not ship with these rendering raw |

Numbers 4 and 5 are the two that can sink the page. If the label comes off either one, the page
is claiming a measured result it does not have, which is exactly the failure Hard Constraint 3
exists to prevent. Render them through a component that cannot omit the word target.

---

## 12. TODO, operator supplied

Add these to the site's `TODO.md` on merge. None of them may be invented.

- `{{SNAPSHOT_ID}}` the openFDA snapshot the worked example is computed from.
- `{{EXAMPLE_CODE}}`, `{{EXAMPLE_DEVICE_NAME}}`, `{{EXAMPLE_CLASS}}` the product code the worked
  example uses, drawn from the allowlist.
- `{{RAW_12M}}`, `{{DEDUP_12M}}`, `{{DUP_RATE}}`, `{{DUP_RATE_CI}}` produced by the first validated
  run, not before.
- `{{GOLD_PAIRS_N}}` the size of the labelled sample per product code.
- `{{PMS_SCOPE}}`, `{{PRICE_BAND_PMS}}`, `{{LEAD_TIME_PMS}}` the pilot terms.
- The FDA citation URLs for claims register rows 7, 8 and 9, each with a `last_verified` date.
- Whether a post-market pilot is a seventh service page or a fold on `/remediate`. This draft
  assumes a fold plus a method child page, which adds no route.

## 13. Ship checklist

- [ ] No client named, no engagement history implied, no testimonial.
- [ ] Every number traced to a row in section 11.
- [ ] Rows 4 and 5 render with the word target attached.
- [ ] No `{{PLACEHOLDER}}` renders raw on a live page.
- [ ] No em dashes anywhere in the rendered copy.
- [ ] Section 8, what is not built yet, still present and not trimmed for length.
- [ ] Banned language grep passes: safe, unsafe, dangerous, problem device, better, worse,
      verified, certified, endorsed, approved, trusted.
- [ ] Disclaimer block renders from the scorecard's own disclaimer list, not retyped.
- [ ] Page loads under the site's existing Lighthouse floor with no new third party request.
