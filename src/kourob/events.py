"""Events: the canonical form of everything a node knows.

Brief reference: section 2 and section 3.1 step 3.

An event is immutable, typed, and provenance-stamped. Pages cite event ids; receipts cite
event ids; the evolve loop reads events. Nothing in the node is true unless an event says
so.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

__milestone__ = "M1"


class Provenance(BaseModel):
    """Where a fact came from, in enough detail to re-derive or blame it.

    Exported with W3C PROV vocabulary (brief section 4.3): `source` is the prov:Entity,
    `activity` the prov:Activity that produced it, `agent` who ran it.
    """

    source: str = Field(description="URI, file path, or upstream node did:key")
    activity: str = Field(description="the loop or tool that produced this event")
    agent: str = Field(description="did:key or user id responsible")
    retrieved_at: datetime
    source_hash: str | None = Field(default=None, description="sha256: of the raw source")
    upstream_events: list[str] = Field(default_factory=list, description="derived-from event ids")


class Event(BaseModel):
    """One immutable typed fact.

    `schema_ref` names the ODCS contract that `payload` validates against. The gate is the
    only writer (AGENTS.md section 4).
    """

    id: str = Field(description="ULID, prefixed evt_")
    schema_ref: str = Field(description="ODCS contract id and version, e.g. shot.v1")
    ts: datetime = Field(description="when the fact became true, ISO 8601 UTC")
    ingested_at: datetime = Field(description="when the node learned it")
    payload: dict[str, Any] = Field(description="validated against schema_ref")
    provenance: Provenance
    novelty: float | None = Field(
        default=None, description="0..1, how much this adds over what the node already has"
    )
    consent: str | None = Field(default=None, description="consent basis if payload carries PII")
    pii: bool = False

    model_config = {"frozen": True}


class QuarantinedEvent(BaseModel):
    """A push that failed the gate, kept with its reason.

    Repeated reasons become schema or rule proposals in the next evolve (brief section 6.3).
    """

    raw: dict[str, Any]
    reason: str
    gate_step: str = Field(description="which gate step rejected it")
    ingested_at: datetime
    provenance: Provenance


__all__ = ["Event", "Provenance", "QuarantinedEvent"]
