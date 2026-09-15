# The MAUDE distinct-event method

The source document held by this node. Each heading below carries exactly one paragraph, because
the gate keys `note.v1` on topic and timestamp: a second paragraph under the same heading arrives as
a contradiction of the first and is quarantined rather than stored. One heading, one claim, one
page. A citation on any answer resolves to `maude-distinct-events.md#<heading>`, a place in this
file, rather than to an opaque event id.

## the question

An RA/QA lead asks a question that sounds like it has a lookup answer: how many adverse events were
reported for this product code in the last twelve months. The FDA public MAUDE search returns a
number in a second, and that number is the count of reports on file rather than the count of events.

## why reports outnumber events

A single event can generate a manufacturer report, a user facility report, and a voluntary report,
filed separately by three parties who never spoke to each other. Follow-up submissions to an earlier
report are separate records again. Identifiers are dirty enough that one device appears under
several spellings of its brand name, so naive grouping does not collapse them.

## why the error matters

Count reports and call them events and every downstream number moves: the trend, the quarter over
quarter comparison, the figure that goes into a complaint trend report or a CAPA input. The error is
systematic rather than random, so it does not average out across a larger window.

## why the corrected number is not published

Correcting the count requires a method, a method requires a validation set, and a validation set
requires somebody to hand-label pairs of reports as the same event or not. That work is unglamorous,
it has to be redone whenever the method changes, and there is no published place to put the result,
so the raw number stays in circulation.

## no denominator

MAUDE contains counts, not rates. Nothing about how many devices are in use is in the file, so no
count in it can be turned into a rate, and differences between product codes reflect market size,
reporting practices, and reporting requirements as much as anything about a device.

## a report is not a finding

An MDR is a report rather than a finding. The FDA does not verify reports, and a report does not
establish that a device caused the event described in it.

## the programme boundary

The FDA has run summary reporting programmes under which certain events were reported in aggregate
rather than as individual public MDRs. Where a product code is affected, counts are not comparable
across that boundary, and the output says so rather than silently joining the series.

## the method

Two passes, both deterministic, both versioned. The goal is an estimate of distinct real-world
events rather than perfect record linkage, and the method states that limit in those words rather
than leaving a reader to infer it.

## exact linkage

Pass one groups records that share an event key where one is present, and groups follow-up
submissions to their initial submission through the shared report number root.

## fuzzy linkage

Pass two works within a single product code. Two records are a candidate pair when the normalised
manufacturer name matches, and the date of event falls within plus or minus 3 days, and the event
type matches, and at least one of the normalised brand name, lot number, or model number matches.

## confirming a pair

A candidate pair is confirmed when the two records share an identical product problems set, or when
their event descriptions reach a MinHash Jaccard similarity of 0.6 or above. Confirmed pairs resolve
into clusters by union-find, and one cluster is one estimated event.

## duplicate rate

Raw reports is the count of records carrying the product code, dedup events is the count of clusters
remaining after both passes, and duplicate rate is one minus dedup events divided by raw reports.
It is reported as an estimate with the method version attached.

## versioning the method

Every figure published from this method carries its method version. The method is never changed
quietly: a change bumps the version, the prior version outputs are kept, and the change is written
into the amendments log.

## the validation set

A sample of candidate pairs per product code is labelled by hand as duplicate, not duplicate, or
unsure, and where more than one person labels, inter-annotator agreement is measured and published
with the result.

## holding the gold out

The labelled set is held out. The clustering code never reads it, and the build fails if it does.

## the acceptance floor

Precision against the labelled set targets 0.85 or above and recall targets 0.70 or above. Both are
design targets rather than measured results, because the labelled set does not exist yet.

## enforcing the floor

The publishing pipeline refuses to deploy a scorecard whose precision sits below the published
floor. That is a build step rather than a promise.

## the fixture rule

Until a real labelled set exists the pipeline runs against a fixture set marked synthetic in its own
header, and the scorecard generator refuses to publish a card built from it, writing the card to a
fixtures directory instead. The pipeline can be tested end to end without one unvalidated number
reaching a published page.

## the review record

A duplicate rate that ends up in a post-market surveillance file has to carry who stood behind it.
The reviewer enters a name and organisation, and both stay in the browser.

## dispositioning the method

The reviewer dispositions three method statements, the deduplication method, the lag exclusions, and
the spike threshold, as accepted, accepted with note, or rejected. The exported file header rows
record the reviewer name, the dispositions, the method version, the source snapshot, and the
timestamp, so the file arrives already carrying its own review record.

## what the numbers may not say

The method never produces a rate, never establishes causation, and never ranks devices or
manufacturers. Every count it produces is an estimate from a published method with a published error
rate, and the comparison surface never uses the words better or worse.

## what is not built yet

The hand-labelled validation set does not exist, so precision and recall are targets rather than
results. Revision behaviour needs several weekly snapshots before it reports anything. Coverage
starts at a small allowlist of product codes rather than the whole database, and spike annotation
matches recalls only, so a spike with no recall match is shown as unannotated rather than explained.
