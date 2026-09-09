# Goal

> Any builder can create a node in one command, connect it to other nodes, and have it
> become cheaper and better at its job with every request it serves, while every answer
> it gives can be traced back to its sources and its cost can be metered along the whole
> chain that produced it.

## Measurable targets for v1.0

| Metric | Target |
|---|---|
| Time from `kourob init` to a node answering over MCP with a cited answer | Under 10 minutes |
| Share of requests served by tier 0 or 1 (rules, cache, distilled model) after 30 days of traffic on the example node | 80 percent or more |
| Cost per request on the example node, day 30 vs day 1 | Down 5x or more |
| Provenance: fraction of answers whose full chain (every node, every source, every model version) is reconstructible from receipts | 100 percent |
| Referral learning: second request for the same out-of-scope topic goes direct (no bridge hop) | Yes, measured by the router test |
| Split: a node receiving a bimodal request distribution auto-proposes a split within one evolve cycle | Yes, measured by the split test |

## Scope discipline

A proposal that does not move one of the metrics above goes to `docs/ideas/`. This is the
single test applied in review. See `docs/brief/07-kourob-development.md` section 15.
