"""Storage for a node. One interface, one v1 backend.

Brief reference: ADR-0001.

Nothing outside this package may open a ``.parquet`` path or a DuckDB connection
directly. CI greps for it (AGENTS.md section 4).
"""

from __future__ import annotations

from kourob.store.base import LOGICAL_TABLES, Store

__milestone__ = "M1"
__all__ = ["LOGICAL_TABLES", "Store"]
