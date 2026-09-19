# The deduplication method, version 0.1

Held by `maude-method`. This cell owns how distinct events are estimated and nothing else. It holds
no validation result and no claim about what the output may be used to say; asked for either, it
refuses and names who does.

## the goal of the method

The method estimates the number of distinct real-world events behind a set of reports. It does not
attempt perfect record linkage, and it says so rather than leaving a reader to infer the limit from
a number that looks exact.

## exact linkage

Pass one groups records that share an event key where one is present, and groups follow-up
submissions to their initial submission through the shared report number root.

## fuzzy linkage

Pass two works within a single product code. Two records are a candidate pair when the normalised
manufacturer name matches, and the date of event falls within plus or minus 3 days, and the event
type matches, and at least one of the normalised brand name, lot number or model number matches.

## confirming a candidate pair

A candidate pair is confirmed when the two records share an identical product problems set, or when
their event descriptions reach a MinHash Jaccard similarity of 0.6 or above.

## clustering

Confirmed pairs are resolved into clusters by union-find, and one cluster counts as one estimated
event.

## duplicate rate

Raw reports is the count of records carrying the product code, dedup events is the count of clusters
remaining after both passes, and duplicate rate is one minus dedup events divided by raw reports.

## versioning the method

Every figure published from this method carries its method version. The method is never changed
quietly: a change bumps the version, the outputs of the prior version are kept, and the change is
written into the amendments log.

## why the corrected number is not already published

Correcting a report count into an event count requires a method, a method requires a validation set,
and a validation set requires somebody to hand-label pairs as the same event or not. That work is
unglamorous, it has to be redone whenever the method changes, and there is no published place to put
the result, so the raw number stays in circulation.
