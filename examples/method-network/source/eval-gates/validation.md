# Validation, and what has actually been measured

Held by `eval-gates`. This cell owns the difference between a target and a result, and it is the
only cell allowed to answer whether the method works. Its answers say which of the two a number is,
every time, because that distinction is the one most often lost between a repository and a page.

## the validation set

A sample of candidate pairs per product code is labelled by hand as duplicate, not duplicate, or
unsure. Where more than one person labels, inter-annotator agreement is measured and published
alongside the result.

## holding the gold out

The labelled set is held out. The clustering code never reads it, and the build fails if it does.

## the precision target

Precision against the labelled set targets 0.85 or above. This is a design target, not a measured
result, because no labelled set exists yet.

## the recall target

Recall against the labelled set targets 0.70 or above. This is a design target, not a measured
result, because no labelled set exists yet.

## what has been measured so far

Nothing. No precision figure, no recall figure, and no duplicate rate for any product code has been
produced from real data by this method. Every number this cell holds is a target awaiting a
validation set.

## enforcing the floor

The publishing pipeline refuses to deploy a scorecard whose precision sits below the published
floor. That is a build step rather than a promise, and it fails closed.

## the fixture rule

Until a real labelled set exists the pipeline runs against a fixture set marked synthetic in its own
header, and the scorecard generator refuses to publish a card built from it, writing the card to a
fixtures directory instead. The pipeline can be exercised end to end without one unvalidated number
reaching a published page.

## the expansion gate

Coverage stays on a small allowlist of product codes until precision against a real labelled set
reaches the floor. Expanding before then would multiply an unmeasured error across the database.
