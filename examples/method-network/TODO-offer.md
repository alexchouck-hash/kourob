# TODO: operator-supplied values on `site/maude.html`

The page carries 10xAnd branding and a pilot offer block. Everything below is the operator's to
supply. None of it may be invented: 10xAnd Phase 1 Hard Constraint 3 allows a number on a page only
if it is a credential, a standard's requirement, a publicly verifiable fact, or an explicit design
target labelled as such.

All of it lives in one place: the `OFFER` object at the top of `site/maude.js`. Nothing else needs
editing, and no value appears anywhere else in the page.

| Key in `OFFER` | Was | Renders today as | Owner |
|---|---|---|---|
| `scope` | `{{PMS_SCOPE}}` | `scope not set` | founder |
| `price` | `{{PRICE_BAND_PMS}}` | `price band not set` | founder |
| `leadTime` | `{{LEAD_TIME_PMS}}` | `lead time not set` | founder |
| `bookUrl` | `{{CALENDLY_URL}}` | `booking link not configured` | founder |

An unset value renders as a visible marker in the 10xAnd accent colour, never as a raw
`{{PLACEHOLDER}}` string. Phase 2 audit gap G4 recorded about 35 raw mustaches rendering mid-sentence
on live pages as a credibility blocker with exactly this audience, so the page states that a term is
not set rather than leaking the template.

## Still open, and not fixable in this file

- **Hosting identity.** This page is served from `alexchouck-hash.github.io`, a personal account that
  identifies the founder. 10xAnd Phase 1 Hard Constraint 1 forbids founder-identifying strings in the
  hosting URL, and Phase 2 records this as gap **G1, a launch blocker** for the 10xAnd site itself.
  The page content is clean: it names no founder, no employer, and no client. The URL is the problem,
  and it is resolved by the neutral-org cutover in Phase 2 §1 or by not pointing 10xAnd traffic here.
  Carrying the branding on this domain was a decision made with that tradeoff on the table.
- **Figures in the method.** Precision 0.85 and recall 0.70 are design targets, and the cell that
  owns them, `eval-gates`, says so in the same sentence as the number. It is the only cell allowed
  to answer whether the method works, and its answer today is that nothing has been measured. Those
  figures may not be restated anywhere as results until a hand-labelled validation set exists.
- **No capture form.** The page has no email capture, so the newsletter disclosure and the double
  opt-in requirement in Phase 1 §1.5 do not apply to it. Adding one brings both back.
