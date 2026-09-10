"""KNP extension URIs and metadata key construction.

Brief reference: docs/protocols/, ADR-0006.

KouroB semantics ride on A2A as declared extensions, not as a `kourob.*` namespace. These
URIs are a public commitment: they appear in agent cards, in the `A2A-Extensions` header,
and as the prefix of every metadata key. Change one and every peer breaks, so they live in
exactly one place.
"""

from __future__ import annotations

from enum import StrEnum

__milestone__ = "M1"


class Ext(StrEnum):
    """The five KNP extension URIs, one per spec."""

    SCOPE = "https://kourob.org/ext/scope/v1"
    RECEIPT = "https://kourob.org/ext/receipt/v1"
    METER = "https://kourob.org/ext/meter/v1"
    REGISTRY = "https://kourob.org/ext/registry/v1"
    OUTCOME = "https://kourob.org/ext/outcome/v1"
    TAP = "https://kourob.org/ext/tap/v1"


#: Which KNP spec documents each extension, for `kourob doctor` and the agent card.
EXT_SPEC = {
    Ext.SCOPE: "KNP-1",
    Ext.RECEIPT: "KNP-2",
    Ext.METER: "KNP-3",
    Ext.REGISTRY: "KNP-4",
    Ext.OUTCOME: "KNP-5",
    Ext.TAP: "KNP-6",
}

#: A2A header a client uses to activate extensions, and the server to echo what it applied.
ACTIVATION_HEADER = "A2A-Extensions"

#: Where a set publishes its signed registry (KNP-4 section 2).
SET_REGISTRY_PATH = "/.well-known/kourob-set.json"


def key(ext: Ext, name: str) -> str:
    """Build a namespaced metadata key, per the A2A convention.

    >>> key(Ext.SCOPE, "route_hints")
    'https://kourob.org/ext/scope/v1/route_hints'
    """
    return f"{ext.value}/{name}"


def activation_header(*exts: Ext) -> str:
    """Render the `A2A-Extensions` header value for the given extensions."""
    return ", ".join(e.value for e in exts)


def parse_activation(header: str) -> list[str]:
    """Parse an `A2A-Extensions` header into URIs, preserving order, dropping blanks."""
    return [part.strip() for part in header.split(",") if part.strip()]


__all__ = [
    "ACTIVATION_HEADER",
    "EXT_SPEC",
    "SET_REGISTRY_PATH",
    "Ext",
    "activation_header",
    "key",
    "parse_activation",
]
