"""The Parquet + DuckDB store.

Brief reference: ADR-0001.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kourob.store.base import LOGICAL_TABLES
from kourob.store.parquet_duckdb import ParquetDuckDBStore


@pytest.fixture
def store(tmp_path: Path) -> ParquetDuckDBStore:
    return ParquetDuckDBStore(tmp_path)


def test_a_heterogeneous_batch_keeps_every_column(store: ParquetDuckDBStore) -> None:
    """The bug this test exists for, and it was silent.

    `pa.Table.from_pylist` infers its schema from the *first* record, so a batch of receipts
    followed by outcomes wrote the receipts' columns and dropped every outcome field —
    leaving signatures over data that was no longer there. Rows are padded to the union of
    keys so the loss is impossible rather than unlikely.
    """
    store.append(
        "receipts",
        [
            {"id": "rcpt_1", "kind": "receipt", "seq": 0, "tier_used": "T0"},
            {"id": "outc_1", "kind": "outcome", "seq": 1, "about": "rcpt_1", "verdict": "accepted"},
        ],
    )

    receipt, outcome = store.scan("receipts", order_by="seq")
    assert receipt["tier_used"] == "T0"
    assert receipt["about"] is None
    assert outcome["about"] == "rcpt_1"
    assert outcome["verdict"] == "accepted"
    assert outcome["tier_used"] is None


def test_an_empty_table_answers_nothing_yet_rather_than_no_such_thing(
    store: ParquetDuckDBStore,
) -> None:
    assert store.query("SELECT count(*) AS n FROM silver").to_pylist() == [{"n": 0}]
    assert store.partitions("silver") == []
    assert store.stats("silver")["rows"] == 0


def test_query_is_read_only(store: ParquetDuckDBStore) -> None:
    store.append("silver", [{"id": "evt_1", "schema_ref": "note.v1"}])
    for sql in ("DELETE FROM silver", "UPDATE silver SET id = 'x'", "DROP VIEW silver"):
        with pytest.raises(ValueError, match="read-only"):
            store.query(sql)


def test_an_unknown_logical_table_is_refused(store: ParquetDuckDBStore) -> None:
    with pytest.raises(ValueError, match="unknown logical table"):
        store.append("whatever", [{"id": "x"}])
    assert "silver" in LOGICAL_TABLES


def test_nested_values_round_trip_through_get_but_stay_queryable(
    store: ParquetDuckDBStore,
) -> None:
    """`query` leaves nested columns as JSON text on purpose: DuckDB can `json_extract`
    them, and decoding would change what a SQL caller asked for."""
    store.append(
        "silver", [{"id": "evt_1", "schema_ref": "note.v1", "payload": {"topic": "bridge", "n": 3}}]
    )
    assert store.get("silver", "evt_1")["payload"] == {"topic": "bridge", "n": 3}
    rows = store.query(
        "SELECT id FROM silver WHERE json_extract_string(payload, '$.topic') = 'bridge'"
    ).to_pylist()
    assert rows == [{"id": "evt_1"}]


def test_named_and_positional_parameters_both_bind(store: ParquetDuckDBStore) -> None:
    """A mined T0 rule binds from named capture groups; making generated SQL depend on
    positional order is a bug waiting for a rule with two parameters."""
    store.append("silver", [{"id": "evt_1", "schema_ref": "note.v1"}])
    assert store.query("SELECT id FROM silver WHERE id = $wanted", {"wanted": "evt_1"}).to_pylist()
    assert store.query("SELECT id FROM silver WHERE id = ?", ["evt_1"]).to_pylist()


def test_compaction_preserves_every_row(store: ParquetDuckDBStore) -> None:
    for i in range(5):
        store.append("silver", [{"id": f"evt_{i}", "schema_ref": "note.v1"}])
    assert store.stats("silver")["parts"] == 5

    store.compact("silver", before="9999-99")

    assert store.stats("silver")["parts"] == 1
    assert store.stats("silver")["rows"] == 5
    assert [r["id"] for r in store.scan("silver")] == [f"evt_{i}" for i in range(5)]
