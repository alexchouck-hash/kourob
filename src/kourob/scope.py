"""Scope: what this node answers, and what it does with everything else.

Brief reference: sections 2 and 3.1 step 2. KNP-1 sections 3 and 6. KNP-0 section 5.

Rules first, model second. The rules here are cheap and explainable, and every decision
records *which* rule decided so the evolve loop can see what the classifier is doing. The T1
scope classifier (M5) attaches behind them and only sees what the rules could not decide.

A refusal is a signal, not a failure. It carries a reason and, whenever the node knows one,
a route — because a node that refuses well makes the network faster.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kourob.manifest import Manifest
from kourob.routes import Route, RouteTable
from kourob.types import RefusalReason, RouteHint, ScopeResult

__milestone__ = "M3"


@dataclass
class ScopeDecision:
    result: ScopeResult
    reason: RefusalReason | None = None
    decided_by: str = "rule:default"
    matched_exclude: str | None = None
    route: Route | None = None
    hints: list[RouteHint] = field(default_factory=list)

    @property
    def in_scope(self) -> bool:
        return self.result is ScopeResult.IN_SCOPE


def _excluded(manifest: Manifest, question: str) -> tuple[str, str | None] | None:
    """The first `excludes` pattern the question matches, and where it should go."""
    lowered = question.lower()
    for i, exclusion in enumerate(manifest.scope.excludes):
        pattern = exclusion.pattern
        try:
            hit = re.search(pattern, lowered, re.IGNORECASE) is not None
        except re.error:
            hit = pattern.lower() in lowered
        if hit:
            return f"rule:excl-{i:03d}", exclusion.refer_to
    return None


def hint_for(route: Route) -> RouteHint:
    return RouteHint(
        node=route.node,
        scope=route.summary,
        endpoint=route.endpoint,
        name=route.name,
        schemas=list(route.schemas),
        cost_credits=route.observed_price,
        latency_ms=route.observed_latency_ms,
        evidence=route.evidence,
    )


def check(
    manifest: Manifest,
    routes: RouteTable,
    question: str,
    *,
    own_did: str,
    hops: list[str],
) -> ScopeDecision:
    """Classify one request before any tier runs.

    Order matters and is the whole design:

    1. **Loop and hop budget** — a request that has already been here, or has travelled too
       far, is refused before anything else is spent on it.
    2. **Declared exclusions** — the node stating, in advance, the things people will
       wrongly bring to it. Matched, this is a referral to the named neighbour, or a reject
       with "not mine and I don't know whose" when `refer_to` is null.
    3. **In scope by default.** Everything else goes to the cascade. If the cascade then
       finds nothing, the route table gets a second look (see `after_miss`).
    """
    if own_did in hops:
        return ScopeDecision(ScopeResult.REJECT, RefusalReason.LOOP, "rule:hops")
    if len(hops) >= manifest.scope.max_hops:
        return ScopeDecision(ScopeResult.REJECT, RefusalReason.HOPS_EXHAUSTED, "rule:hops")

    excluded = _excluded(manifest, question)
    if excluded is not None:
        decided_by, refer_to = excluded
        route = routes.get(refer_to) if refer_to else routes.lookup(question)
        if route is None:
            return ScopeDecision(
                ScopeResult.REJECT,
                RefusalReason.OUT_OF_SCOPE,
                decided_by,
                matched_exclude=decided_by,
            )
        return ScopeDecision(
            ScopeResult.REFERRAL,
            decided_by=decided_by,
            matched_exclude=decided_by,
            route=route,
            hints=[hint_for(route)],
        )

    return ScopeDecision(ScopeResult.IN_SCOPE, decided_by="rule:default")


def after_miss(routes: RouteTable, question: str) -> ScopeDecision:
    """The cascade found nothing. Is this somebody else's job?

    A referral here is weaker than one from a declared exclusion — it rests on the route
    table's guess, not the node's declaration — so it carries the route's evidence receipt
    and the caller can weigh it. No candidate means `out_of_scope` with nothing named,
    which is a legitimate and useful answer. Guessing would be worse.
    """
    route = routes.lookup(question)
    if route is None:
        return ScopeDecision(ScopeResult.REJECT, RefusalReason.OUT_OF_SCOPE, "rule:no-route")
    return ScopeDecision(
        ScopeResult.REFERRAL, decided_by="rule:route-match", route=route, hints=[hint_for(route)]
    )


__all__ = ["ScopeDecision", "after_miss", "check", "hint_for"]
