"""The Store interface.

Brief reference: section 9 and ADR-0001.

The point of this interface is that a row-versioned backend (Dolt) or a server backend
(Postgres) can implement it without the interface changing. So: no method exposes a file
path, a partition layout, or a database connection. Callers that need SQL pass a SQL
string against *logical* table names, which the backend resolves.

Logical tables: ``silver``, ``quarantine``, ``requests``, ``receipts``, ``routes``,
``calls``, ``accounts``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

__milestone__ = "M1"

LOGICAL_TABLES = (
    "silver",
    "gold",
    "quarantine",
    "requests",
    "receipts",
    "routes",
    "calls",
    "accounts",
)


class Store(ABC):
    """Append-only storage for a node.

    v1 is single-process: no concurrent writers (ADR-0001, Consequences). Implementations
    may assume one writer and many in-process readers.
    """

    @abstractmethod
    def append(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        """Append rows to a logical table. Returns the number of rows written.

        Raises ValueError if `table` is not in LOGICAL_TABLES.
        """

    @abstractmethod
    def query(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> Any:
        """Run read-only SQL against the logical tables. Returns an Arrow table.

        `params` may be positional or named. Named is what a mined T0 rule produces, since
        its bindings come from named capture groups, and positional order is not something a
        generated rule should have to be careful about.

        Implementations must reject statements that write.
        """

    @abstractmethod
    def get(self, table: str, row_id: str) -> dict[str, Any] | None:
        """Fetch one row by its id column. Returns None if absent."""

    @abstractmethod
    def partitions(self, table: str) -> list[str]:
        """List partition keys for a table, oldest first."""

    @abstractmethod
    def compact(self, table: str, before: str | None = None) -> int:
        """Compact partitions older than `before`. Returns partitions compacted."""

    @abstractmethod
    def stats(self, table: str) -> dict[str, Any]:
        """Row count, byte size, and partition span. Used by prune and by meter report."""


__all__ = ["LOGICAL_TABLES", "Store"]
