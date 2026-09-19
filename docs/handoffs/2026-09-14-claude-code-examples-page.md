# 2026-09-14 — claude-code — the examples page (kb-4ym)

## Done

- **`site/examples.html`** on `feat/public-site` (commit `0731978`). The three worked examples as a
  ladder — `trooth-node` (1 cell) → `trooth-set` (4) → `trooth-network` (7) — with the network as
  the centrepiece:
  - an interactive SVG topology: click a cell for its declared scope, holdings, source and licence;
    pick one of four example questions and only the cells that question actually touches stay lit;
  - the two-referral hop trace (`trooth-desk` → `weather-desk` → `nws-node`) with the real
    `kourob query` output from a freshly built network;
  - the runbook (`build.py`, a query, the dashboard), the honest-fixtures note, and six cards on
    what the network demonstrates.
- Linked from the nav, the hero CTA, the footer, `site/sitemap.xml` and `site/llms.txt` (a new
  "Worked Examples: Networks of Nodes" section), so the page is reachable from the site root.
- Verified in a local preview at 1400×900 in both themes: no console errors, topology renders,
  route highlighting and the detail panel work, `app.js` theme toggle and copy buttons work
  unchanged.

## Not done

- **The page is not live.** The `github-pages` environment now has a deployment branch policy
  allowing only `main`, so the `deploy-site` run from `feat/public-site` was rejected
  (run `34908835309`). `main` has no `site/` directory at all — the live site is still the
  2026-09-11 deploy. The human chose the merge path: **merge PR #2 and Pages deploys from `main`**
  as its source is already configured.
- PR #2 is `MERGEABLE` but `BLOCKED`: `main` requires one approving review and `enforce_admins` is
  on, so the owner cannot merge unreviewed. `ci` passes; the failing `deploy` check is the rejection
  above and is not a required check.

## Surprises

- `examples/trooth-network/` was being written by another agent session in the same worktree while
  this task ran, so nothing under `examples/` was touched here. The page's node counts, scopes,
  exclusion patterns and credits were read from that example's `build.py` and from an actual build,
  not invented.
- A local `.claude/launch.json` entry added here for previewing the site (`kourob-site-preview`,
  `python -m http.server` over `kourob-site/site`) was swept into that session's commit `9ed5379`.
  Harmless; delete it if it is noise.

## Open questions

- Should `site/` move to `main` permanently (Pages' configured source), leaving `feat/public-site`
  for drafts? Right now the only way to publish anything is a merge to `main`, which makes the
  branch's name misleading.
- The page describes `trooth-network`, which is not on `main` yet. Nothing on the page links to a
  path that must exist on `main` — the GitHub links point at `examples/` and the two older examples
  — but once `trooth-network` lands, deep links to it would be worth adding.

## Resume

```bash
cd C:/Users/houck/kourob-site
python -m http.server 4400 --directory site   # then open http://localhost:4400/examples.html
gh pr view 2 --json mergeable,mergeStateStatus
gh run list --workflow=deploy-site.yml --limit 3
```

After PR #2 merges, confirm the deploy and the live link:

```bash
gh run list --workflow=deploy-site.yml --limit 1
curl -sI https://alexchouck-hash.github.io/kourob/examples.html | head -1
```
