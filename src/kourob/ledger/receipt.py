"""The receipt: the unit of provenance and metering.

Brief reference: section 4.1.

One receipt per request. Receipts hash the request and the response; they never store
them (brief section 15, privacy). The `prev` field makes the node ledger a hash chain;
`upstream` makes the network a DAG that `kourob trace` can walk.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from kourob.types import ScopeResult, Tier

__milestone__ = "M1"

#: Fields covered by `sig`, in this order. Changing this list is a breaking change to the
#: ledger format and needs an ADR.
SIGNED_FIELDS = (
    "id",
    "node",
    "caller",
    "request_hash",
    "response_hash",
    "scope_result",
    "tier_used",
    "model_version",
    "citations",
    "upstream",
    "cost_credits",
    "price_credits",
    "ts",
    "prev",
)


class Receipt(BaseModel):
    """A signed record of one request."""

    id: str = Field(description="ULID, prefixed rcpt_")
    node: str = Field(description="did:key of the answering node")
    caller: str = Field(description="did:key of a node, or user:<id>")
    request_hash: str = Field(description="sha256: of the canonical request")
    response_hash: str = Field(description="sha256: of the canonical response")
    scope_result: ScopeResult
    tier_used: Tier | None = Field(
        default=None, description="None when the request was referred or rejected"
    )
    model_version: str = Field(
        description="student-s@0.4.2 | frontier:<vendor>:<model> | rule:<id>"
    )
    citations: list[str] = Field(default_factory=list, description="event ids")
    upstream: list[str] = Field(
        default_factory=list, description="receipt ids from other nodes this answer used"
    )
    cost_credits: float = Field(description="measured, not estimated: what it cost the node")
    price_credits: float = Field(description="what the caller was charged")
    ts: datetime
    prev: str = Field(description="sha256: of the previous receipt on this node")
    sig: str = Field(description="ed25519 signature over SIGNED_FIELDS")

    model_config = {"frozen": True}


__all__ = ["SIGNED_FIELDS", "Receipt"]
