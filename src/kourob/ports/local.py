"""The local transport: a neighbour that lives on this disk.

Brief reference: KNP-9 section 1 — `kourob connect ./sibling-cell`.

The first transport, on purpose. Every protocol from KNP-1 onward was untested against a
second party until this existed, and a transport that needs no server lets the whole loop —
scope check, referral, bridge, chained receipts, route learning, hop lists — be exercised in
a test with two directories. HTTP over A2A attaches behind the same `Neighbour` contract and
nothing above it changes.

Even locally, nothing crosses by import. A local neighbour is opened by path and asked over
`serve.answer`, exactly as a remote one would be asked over the wire, and it writes its own
receipt in its own ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kourob.routes import Route
from kourob.types import Answer

__milestone__ = "M3"


class Neighbour(Protocol):
    """Anything a node can ask a question of."""

    did: str
    endpoint: str

    def ask(self, question: str, *, caller: str, hops: list[str]) -> Answer: ...


@dataclass
class LocalNeighbour:
    """A node on disk, reached by path."""

    path: Path
    did: str
    endpoint: str

    @classmethod
    def open(cls, path: Path | str) -> LocalNeighbour:
        from kourob.node import open_node

        node = open_node(path)
        return cls(path=Path(path), did=node.did, endpoint=str(Path(path).resolve()))

    def ask(self, question: str, *, caller: str, hops: list[str]) -> Answer:
        from kourob import serve
        from kourob.node import open_node

        return serve.answer(open_node(self.path), question, caller=caller, hops=list(hops))


class UnreachableNeighbourError(RuntimeError):
    """A route whose endpoint this build cannot speak to."""


def resolve(route: Route) -> Neighbour:
    """Turn a route into something that can be asked.

    Endpoint scheme decides the transport. A path is local. `http(s)://` is the A2A port,
    which lands with `kb-imt`; until then a remote route is refused rather than silently
    treated as local, because the failure mode of guessing a transport is a request that
    goes nowhere and a receipt that says it went somewhere.
    """
    endpoint = route.endpoint or ""
    if endpoint.startswith(("http://", "https://")):
        raise UnreachableNeighbourError(
            f"{route.node} is at {endpoint}, and the HTTP transport is not built yet (kb-imt)"
        )
    if not endpoint or not Path(endpoint).exists():
        raise UnreachableNeighbourError(f"{route.node} has no reachable endpoint ({endpoint!r})")
    return LocalNeighbour(path=Path(endpoint), did=route.node, endpoint=endpoint)


__all__ = ["LocalNeighbour", "Neighbour", "UnreachableNeighbourError", "resolve"]
