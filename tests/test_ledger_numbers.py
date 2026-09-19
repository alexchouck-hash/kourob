"""A receipt must still verify after a round trip through storage.

The signature covers `signed_view`, and `identity.canonical` is plain `json.dumps`, so an
int and a float that happen to be equal do not serialise to the same bytes: `0` is `0` and
`0.0` is `0.0`. The store keeps `cost_credits` in one column, so once any receipt has put a
float there, a later receipt signed while that field held a Python `int` reads back holding
a `float`, and its own signature no longer verifies.

A refusal hits this every time, because a refused request costs exactly `0` and the caller
is charged nothing. That is the worst possible place for it: KNP-0 I1 says a node that
cannot write a record must fail rather than answer without one, and plan 06 section 12 puts
"a refusal that names who to ask" in the proof stack. A refusal whose receipt cannot be
verified is not evidence of anything.
"""

from __future__ import annotations

import pytest

from kourob import identity, serve
from kourob import node as node_mod
from kourob.ledger.chain import Ledger, fields_for, signed_view
from kourob.store.parquet_duckdb import ParquetDuckDBStore

NOTE = (
    '{"schema_ref": "note.v1", "topic": "a-held-fact", '
    '"body": "A fact this cell holds, so that its silver is not empty and the note-lookup '
    'rule has a typed column to bind against.", "source": "test", '
    '"ts": "2026-09-15T00:00:00Z"}'
)


@pytest.fixture
def node(node_dir):
    """A cell holding one note, which is the smallest cell that can also refuse."""
    node_mod.init(node_dir, name="ledger-numbers", scope="one held fact and nothing else")
    cell = node_mod.open_node(node_dir)
    report = cell.gate.ingest_lines([NOTE], source="test")
    assert report.accepted == 1, report.reasons
    return node_mod.open_node(node_dir)


def _ledger(node):
    store = ParquetDuckDBStore(node.dir, partition_by=node.manifest.store.partition_by)
    return Ledger(node.dir, store, node.did)


def _unverified(node) -> list[str]:
    """Ids of every record in the chain whose own signature does not check out."""
    bad = []
    for record in _ledger(node).records():
        view = signed_view(record, fields_for(record.get("kind", "receipt")))
        if not identity.verify(node.did, view, record["sig"]):
            bad.append(record["id"])
    return bad


def _receipt(node, receipt_id: str, cost, price) -> None:
    _ledger(node).append(
        "receipt",
        {
            "id": receipt_id,
            "caller": "test",
            "request_hash": "sha256:a",
            "response_hash": "sha256:b",
            "scope_result": "reject",
            "reason": "out_of_scope",
            "citations": [],
            "upstream": [],
            "hops": [node.did],
            "cost_credits": cost,
            "price_credits": price,
            "ts": "2026-09-15T00:00:00+00:00",
        },
    )


def test_an_int_credit_after_a_float_one_still_verifies(node):
    """The bug, reduced.

    The float receipt goes first so the column is a double by the time the int arrives,
    which is the ordering every real node produces: answers cost fractions, refusals cost
    nothing at all.
    """
    _receipt(node, "rcpt_float_cost", 0.00005, 0.0001)
    _receipt(node, "rcpt_int_cost", 0, 0)
    assert _unverified(node) == []


def test_the_receipt_a_refusal_writes_verifies(node):
    """The bug as a caller meets it: get one answer, then ask for something nothing holds."""
    serve.answer(node, "what is a-held-fact", caller="test")
    refused = serve.answer(node, "something no cell on earth holds, about nothing", caller="test")
    assert refused.citations == []
    assert refused.receipt_id, "a refusal must still be receipted (KNP-0 I1)"
    assert _unverified(node) == []
