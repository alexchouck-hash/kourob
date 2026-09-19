# What MAUDE structurally is

Held by `fda-facts`. These are properties of the dataset, not of any method applied to it, and
they fix the ceiling on what any downstream number can honestly claim. One heading, one claim.

## no denominator

MAUDE contains counts, not rates. Nothing about how many devices are in use appears anywhere in the
file, so no count drawn from it can be converted into a rate, and differences between product codes
reflect market size, reporting practices and reporting requirements as much as anything about a
device.

## a report is not a finding

An MDR is a report rather than a finding. The FDA does not verify the reports it receives, and the
existence of a report does not establish that a device caused the event described in it.

## the summary reporting boundary

The FDA has run summary reporting programmes under which certain events were reported in aggregate
rather than as individual public MDRs. Where a product code is affected, counts on either side of
that boundary are not comparable, and a series that joins them without saying so is wrong in a way
no method can correct.

## one event, several reporters

A single real-world event can produce a manufacturer report, a user facility report and a voluntary
report, filed separately by three parties who never spoke to each other. Each arrives as its own
record, so the report count exceeds the event count before any error is made.

## follow-ups are separate records

A follow-up submission to an earlier report is stored as its own record rather than as a revision of
the original, so a single well-documented event accumulates records over time without anything new
having happened.

## identifiers are dirty

Brand names, model numbers and manufacturer names arrive as free text with no enforced vocabulary,
so one device appears under several spellings. Grouping on any of those fields naively will not
collapse the records that belong together.
