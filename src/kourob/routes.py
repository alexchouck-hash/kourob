"""Routes: what this node knows about other nodes, and how sure it is.

Brief reference: sections 3.2 and 7. KNP-4 section 3, KNP-9 sections 1 and 3.

A connection is data, not code. One row per neighbour, learned from a `connect`, a referral
or a bridge, and never from an import. Strength rises on success and decays always, so the
table is a picture of what currently works rather than an archive of what once did, and its
size is bounded by real traffic.

The store is append-only, so a route is updated by appending a newer row; `load` keeps the
latest per key. That is a little wasteful and completely auditable, which is the right
trade for a table that decides where money goes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob.manifest import PrunePolicy
from kourob.store import Store

__milestone__ = "M3"

SOURCE_CONNECT = "connect"
SOURCE_REFERRAL = "referral"
SOURCE_BRIDGE = "bridge"
SOURCE_REGISTRY = "registry"

_WORD = re.compile(r"[a-z0-9][a-z0-9-]{2,}")


def keywords_of(summary: str) -> list[str]:
    """The words a neighbour's scope summary is made of, for matching questions against."""
    return sorted(set(_WORD.findall(summary.lower())))[:24]


@dataclass
class Route:
    node: str
    endpoint: str
    name: str = ""
    summary: str = ""
    schemas: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    strength: float = 0.5
    observed_price: float | None = None
    observed_latency_ms: float | None = None
    last_success: str | None = None
    last_failure: str | None = None
    source: str = SOURCE_CONNECT
    evidence: str | None = None
    successes: int = 0
    failures: int = 0

    @property
    def key(self) -> str:
        return self.node

    def score(self, now: datetime | None = None) -> float:
        """KNP-4 section 3: observation beats advertisement.

        `observed_price` and latency come from receipts this node actually saw. A neighbour
        that overquotes loses score without anyone adjudicating a dispute.
        """
        price = max(self.observed_price or 0.0, 1e-6)
        latency = 1.0 + (self.observed_latency_ms or 0.0) / 1000.0
        return self.strength / (price * latency)

    def matches(self, question: str) -> int:
        """How many of the neighbour's declared words appear in the question."""
        words = set(_WORD.findall(question.lower()))
        stems = {s.split(".")[0].lower() for s in self.schemas}
        return len(words & (set(self.keywords) | stems))

    def as_row(self) -> dict[str, Any]:
        row = dict(self.__dict__)
        row["schemas"] = ",".join(self.schemas)
        row["keywords"] = ",".join(self.keywords)
        row["id"] = ev.new_id("rt_")
        return row

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Route:
        data = {k: v for k, v in row.items() if k in cls.__dataclass_fields__}
        data["schemas"] = [s for s in str(row.get("schemas") or "").split(",") if s]
        data["keywords"] = [s for s in str(row.get("keywords") or "").split(",") if s]
        return cls(**data)


class RouteTable:
    """The synapses. Load, look up, reinforce, decay, learn."""

    def __init__(self, store: Store, policy: PrunePolicy | None = None) -> None:
        self.store = store
        self.policy = policy or PrunePolicy()
        self.routes: dict[str, Route] = {}
        self._load()

    @classmethod
    def load(cls, node_dir: Path | str) -> RouteTable:
        from kourob.node import open_node

        node = open_node(node_dir)
        return cls(node.store, node.manifest.prune)

    def _load(self) -> None:
        if self.store.stats("routes")["rows"] == 0:
            return
        for row in self.store.scan("routes", order_by="id"):
            route = Route.from_row(row)
            self.routes[route.key] = route  # later rows win: id order is time order

    def save(self, route: Route) -> None:
        self.routes[route.key] = route
        self.store.append("routes", [route.as_row()])

    def all(self) -> list[Route]:
        return sorted(self.routes.values(), key=lambda r: -r.score())

    def get(self, node: str) -> Route | None:
        return self.routes.get(node)

    def lookup(self, question: str) -> Route | None:
        """The best neighbour for a question, or None. Best = most matches, then score."""
        floor = self.policy.prune_floor
        candidates = [
            (r.matches(question), r.score(), r) for r in self.routes.values() if r.strength > floor
        ]
        candidates = [c for c in candidates if c[0] > 0]
        if not candidates:
            return None
        candidates.sort(key=lambda c: (-c[0], -c[1]))
        return candidates[0][2]

    def reinforce(
        self,
        node: str,
        *,
        success: bool,
        price: float | None = None,
        latency_ms: float | None = None,
        evidence: str | None = None,
    ) -> Route | None:
        """Hebbian update (KNP-9 section 3). Failure is punished harder than success is
        rewarded, and everything fades on `decay`."""
        route = self.routes.get(node)
        if route is None:
            return None
        stamp = ev.now().isoformat()
        if success:
            route.strength += self.policy.hebbian_alpha * (1.0 - route.strength)
            route.successes += 1
            route.last_success = stamp
            if evidence:
                route.evidence = evidence
            if price is not None:
                route.observed_price = price
            if latency_ms is not None:
                route.observed_latency_ms = latency_ms
        else:
            route.strength *= 1.0 - self.policy.hebbian_beta
            route.failures += 1
            route.last_failure = stamp
        self.save(route)
        return route

    def decay(self) -> int:
        """One window's fade. Called by prune. Returns how many fell below the floor."""
        fallen = 0
        for route in list(self.routes.values()):
            route.strength *= self.policy.decay_per_window
            if route.strength < self.policy.prune_floor:
                fallen += 1
            self.save(route)
        return fallen

    def learn(self, hints: list[Any], *, source: str = SOURCE_REFERRAL) -> list[Route]:
        """Adopt route hints from an answer.

        This is how the network finds short paths: nobody computes them, every caller learns
        one hop at a time from receipts it already paid for (KNP-1 section 5.2).
        """
        learned = []
        for hint in hints:
            data = hint if isinstance(hint, dict) else hint.model_dump()
            node = data.get("node")
            if not node:
                continue
            route = self.routes.get(node) or Route(
                node=node,
                endpoint=str(data.get("endpoint") or ""),
                name=str(data.get("name") or ""),
                summary=str(data.get("scope") or ""),
                source=source,
                strength=0.4,
            )
            if data.get("endpoint"):
                route.endpoint = str(data["endpoint"])
            if data.get("schemas"):
                route.schemas = list(data["schemas"])
            if route.summary and not route.keywords:
                route.keywords = keywords_of(route.summary)
            if data.get("cost_credits") is not None:
                route.observed_price = float(data["cost_credits"])
            if data.get("evidence"):
                route.evidence = str(data["evidence"])
            self.save(route)
            learned.append(route)
        return learned


__all__ = [
    "SOURCE_BRIDGE",
    "SOURCE_CONNECT",
    "SOURCE_REFERRAL",
    "SOURCE_REGISTRY",
    "Route",
    "RouteTable",
    "keywords_of",
]
