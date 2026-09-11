"""The v1 Store backend: append-only Parquet, partitioned by month, queried with DuckDB.

Brief reference: ADR-0001.

Zero infrastructure: no server, no daemon, no migration step. A node is one process and one
writer, which is written into the manifest as a constraint rather than discovered later.

Nothing outside this module opens a Parquet path or a DuckDB connection. `tests/test_rails.py`
enforces that, and the reason is ADR-0001: a row-versioned backend must be able to replace
this file without any caller changing.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from ulid import ULID

from kourob.store.base import LOGICAL_TABLES, Store

__milestone__ = "M1"

#: Logical table name to its directory, relative to the node root. Callers never see these.
TABLE_PATHS = {
    "silver": "data/silver",
    "gold": "data/gold",
    "quarantine": "data/quarantine",
    "requests": "logs/requests",
    "receipts": "ledger/receipts",
    "routes": "routes",
    "calls": "logs/calls",
    "accounts": "ledger/accounts",
}

#: Parts per table before an append folds them. Each append writes one Parquet part; a
#: query reads them all. Sixty-four is small enough to keep reads fast and large enough
#: that folding costs a fraction of the writes it follows.
AUTO_COMPACT_PARTS = 64

#: Statements a read-only query may begin with. Everything else is refused.
_READ_PREFIXES = ("select", "with", "describe", "explain", "summarize", "pragma", "show")

#: Columns stored as canonical JSON because Parquet has no native map-of-anything.
_JSON_COLUMNS = ("payload", "provenance", "detail", "evidence", "metadata", "raw")


class ParquetDuckDBStore(Store):
    """Append-only Parquet under a node directory, with DuckDB for reads."""

    def __init__(self, node_dir: Path | str, *, partition_by: str = "month") -> None:
        self.node_dir = Path(node_dir)
        self.partition_by = partition_by
        self._conn: duckdb.DuckDBPyConnection | None = None
        #: Per table, the part list the current view was built over. Re-registering every
        #: view on every query re-globbed seven directories per request; comparing part
        #: lists makes a query over an unchanged table free.
        self._registered: dict[str, tuple[str, ...]] = {}
        self._parts_cache: dict[str, list[Path]] = {}
        self._row_counts: dict[str, int] = {}

    # ------------------------------------------------------------------ internals

    def _dir(self, table: str) -> Path:
        if table not in LOGICAL_TABLES:
            raise ValueError(f"unknown logical table {table!r}; expected one of {LOGICAL_TABLES}")
        return self.node_dir / TABLE_PATHS[table]

    def _partition_key(self, when: datetime | None = None) -> str:
        when = when or datetime.now(UTC)
        return when.strftime("%Y-%m") if self.partition_by == "month" else when.strftime("%Y")

    def _parts(self, table: str) -> list[Path]:
        """The Parquet parts of a table, globbed once and cached until this store writes.

        ADR-0001 makes a node a single writer, so the only thing that changes a table's
        part list is this object's own `append` or `compact` - both invalidate. Globbing on
        every query was a quarter of a million `stat` calls in two hundred requests.
        """
        cached = self._parts_cache.get(table)
        if cached is not None:
            return cached
        root = self._dir(table)
        parts = sorted(root.glob("*/*.parquet")) if root.exists() else []
        self._parts_cache[table] = parts
        return parts

    def _invalidate(self, table: str) -> None:
        self._parts_cache.pop(table, None)
        self._row_counts.pop(table, None)

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(":memory:")
        return self._conn

    def _register_views(self) -> None:
        """Expose each logical table as a DuckDB view over its Parquet parts.

        A table with no parts is registered as an empty view rather than left missing, so a
        query against a young node returns no rows instead of an error. "Nothing yet" and
        "no such thing" are different answers and callers should not have to tell them apart.
        """
        for table in LOGICAL_TABLES:
            parts = self._parts(table)
            signature = tuple(p.as_posix() for p in parts)
            if self._registered.get(table) == signature:
                continue  # unchanged since last query: the view is still right
            if parts:
                paths = ", ".join(f"'{p}'" for p in signature)
                self.conn.execute(
                    f"CREATE OR REPLACE VIEW {table} AS "
                    f"SELECT * FROM read_parquet([{paths}], union_by_name=true)"
                )
            else:
                self.conn.execute(
                    f"CREATE OR REPLACE VIEW {table} AS SELECT NULL AS id WHERE FALSE"
                )
            self._registered[table] = signature

    @staticmethod
    def _encode(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten nested values to canonical JSON, and give every row the same columns.

        The second half is not tidiness. `pa.Table.from_pylist` infers its schema from the
        first record, so appending a batch whose later rows carry columns the first one
        lacks **silently drops them**. That is how a batch of receipts followed by outcomes
        lost every outcome field, leaving signatures over data that was no longer there.
        Padding to the union of keys makes the loss impossible rather than unlikely.
        """
        materialised = list(rows)
        encoded_rows: list[dict[str, Any]] = []
        for row in materialised:
            encoded = dict(row)
            for col, value in row.items():
                nested = isinstance(value, list) and value and isinstance(value[0], dict)
                already_text = isinstance(value, str)
                if (col in _JSON_COLUMNS and not already_text) or isinstance(value, dict) or nested:
                    # A JSON column handed in as text is stored as-is. Encoding it again
                    # would wrap it in a second layer that `_decode` unwraps only once,
                    # and the caller gets back a string where it wrote a list.
                    encoded[col] = json.dumps(value, sort_keys=True, default=str)
            encoded_rows.append(encoded)

        columns: dict[str, None] = {}
        for row in encoded_rows:
            columns.update(dict.fromkeys(row))
        return [{col: row.get(col) for col in columns} for row in encoded_rows]

    # -------------------------------------------------------------------- Store API

    def append(self, table: str, rows: Iterable[dict[str, Any]]) -> int:
        encoded = self._encode(rows)
        if not encoded:
            return 0
        part_dir = self._dir(table) / self._partition_key()
        part_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.Table.from_pylist(encoded),
            part_dir / f"part-{ULID()}.parquet",
            compression="zstd",
        )
        self._invalidate(table)
        if len(self._parts(table)) > AUTO_COMPACT_PARTS:
            # One part per append is right for an audit trail and wrong for a query: a view
            # over thousands of tiny files is what turned a month of replayed traffic into
            # hours. Fold them once the count gets silly; the rows and their order survive.
            self.compact(table, before="9999-99")
        return len(encoded)  # the next query sees a new part list and rebuilds this view

    def query(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> pa.Table:
        stripped = sql.lstrip().lower()
        if not stripped.startswith(_READ_PREFIXES):
            raise ValueError(
                "Store.query is read-only. Writes go through append(), and silver and gold "
                "are written only by gate.py."
            )
        self._register_views()
        if params is None:
            bound: Any = None
        elif isinstance(params, Mapping):
            bound = dict(params)
        else:
            bound = list(params)
        return self.conn.execute(sql, bound).to_arrow_table()

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        """Inverse of `_encode`. Applied on the dict-returning paths only.

        `query` deliberately leaves nested columns as JSON text: DuckDB can `json_extract`
        them, and decoding would change what a SQL caller asked for.
        """
        out = dict(row)
        for col in _JSON_COLUMNS:
            if isinstance(out.get(col), str):
                with contextlib.suppress(json.JSONDecodeError):
                    out[col] = json.loads(out[col])
        return out

    def get(self, table: str, row_id: str) -> dict[str, Any] | None:
        result = self.query(f"SELECT * FROM {table} WHERE id = ? LIMIT 1", [row_id])
        rows = result.to_pylist()
        return self._decode(rows[0]) if rows else None

    def scan(self, table: str, *, order_by: str = "id") -> list[dict[str, Any]]:
        """Every row in a table, decoded, in order. For hash chains and small tables."""
        return [
            self._decode(r)
            for r in self.query(f"SELECT * FROM {table} ORDER BY {order_by}").to_pylist()
        ]

    def partitions(self, table: str) -> list[str]:
        root = self._dir(table)
        if not root.exists():
            return []
        return sorted(p.name for p in root.iterdir() if p.is_dir())

    def compact(self, table: str, before: str | None = None) -> int:
        """Rewrite each partition's many small parts as one. Append-only is preserved."""
        compacted = 0
        for partition in self.partitions(table):
            if before and partition >= before:
                continue
            part_dir = self._dir(table) / partition
            parts = sorted(part_dir.glob("*.parquet"))
            if len(parts) < 2:
                continue
            paths = ", ".join(f"'{p.as_posix()}'" for p in parts)
            merged = self.conn.execute(
                f"SELECT * FROM read_parquet([{paths}], union_by_name=true)"
            ).to_arrow_table()
            target = part_dir / f"part-{ULID()}.parquet"
            pq.write_table(merged, target, compression="zstd")
            for old in parts:
                old.unlink()
            compacted += 1
        self._conn = None
        self._registered = {}
        self._parts_cache = {}
        self._row_counts = {}
        return compacted

    def stats(self, table: str) -> dict[str, Any]:
        parts = self._parts(table)
        partitions = self.partitions(table)
        # Counted once per write, by DuckDB. Opening every part's footer on every call was
        # fifty thousand `ParquetFile` constructions in two hundred requests.
        if table not in self._row_counts:
            if parts:
                self._register_views()
                count = self.conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()
                self._row_counts[table] = int(count[0] if count else 0)
            else:
                self._row_counts[table] = 0
        rows = self._row_counts[table]
        return {
            "table": table,
            "rows": rows,
            "parts": len(parts),
            "bytes": sum(p.stat().st_size for p in parts),
            "partitions": len(partitions),
            "first_partition": partitions[0] if partitions else None,
            "last_partition": partitions[-1] if partitions else None,
        }


__all__ = ["TABLE_PATHS", "ParquetDuckDBStore"]
