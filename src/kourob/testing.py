"""Fixtures the evals and tests build nodes from.

Brief reference: DEFAULTS.md — no network in unit tests; model calls go through the
runner's `local` adapter.

These build **synthetic traffic**, not synthetic nodes: the manifest, gate, ledger and
store are the real ones, and only the demand is invented. A fixture that stubbed the node
would prove nothing about the node.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob import manifest as manifest_mod
from kourob import node as node_mod
from kourob.ledger.chain import RECORD_OUTCOME, RECORD_RECEIPT
from kourob.ledger.outcome import OutcomeSource, Verdict
from kourob.ledger.outcomes import settle_key
from kourob.request_log import RequestRecord
from kourob.types import Tier

__milestone__ = "M4"

DEFAULT_CAPACITY = 100


def synthetic_request_log(
    tmp_path: Path | str,
    *,
    clusters: dict[str, float],
    days: int = 14,
    demand_factor: float = 0.0,
    settle_rate: float = 1.0,
    accept_rate: float = 1.0,
    declared_schemas: list[str] | None = None,
    tier: Tier = Tier.T3,
    cost_per_request: float = 0.02,
    capacity_window: int = DEFAULT_CAPACITY,
    name: str = "synthetic",
) -> Path:
    """A node whose request log looks like the demand you describe.

    `clusters` maps a schema id to its share of traffic. `demand_factor` sets the volume
    relative to `capacity_window`, so a caller says "1.4x over capacity" rather than
    computing a request count.

    Receipts and outcomes are real and signed — the ledger a test reasons about has to be
    the ledger the code writes, or the test is measuring the fixture.
    """
    target = Path(tmp_path) / name
    node = node_mod.init(target, scope=f"synthetic: {', '.join(clusters)}")

    schemas = declared_schemas if declared_schemas is not None else list(clusters)
    node.manifest.scope.schemas = list(schemas)
    node.manifest.pricing.capacity_window = capacity_window
    manifest_mod.save(target, node.manifest)
    node = node_mod.open_node(target)

    volume = max(1, round(capacity_window * (1.0 + demand_factor)))
    end = datetime.now(UTC)
    start = end - timedelta(days=days)

    entries: list[tuple[str, dict[str, Any]]] = []
    rows: list[dict[str, Any]] = []
    settled_receipts: list[tuple[str, Verdict]] = []

    index = 0
    for schema, share in clusters.items():
        count = max(1, round(volume * share))
        for i in range(count):
            stamp = start + (end - start) * (index / max(1, volume))
            receipt_id = ev.new_id(ev.RECEIPT_PREFIX)
            question = f"what is {schema.split('.')[0]} {i}"
            key = settle_key(schema, {"n": i})
            entries.append(
                (
                    RECORD_RECEIPT,
                    _receipt_body(
                        node.did, receipt_id, schema, tier, cost_per_request, stamp, key, i
                    ),
                )
            )
            rows.append(
                _request_row(receipt_id, schema, tier, cost_per_request, stamp, question, key, i)
            )
            if i / count < settle_rate:
                verdict = Verdict.ACCEPTED if i / count < accept_rate else Verdict.CORRECTED
                settled_receipts.append((receipt_id, verdict))
            index += 1

    # One extend for the receipts, one for the outcomes. Calling extend per record would
    # re-read the chain each time, which is quadratic and was how this fixture first hung.
    node.ledger.extend(
        entries
        + [
            (
                RECORD_OUTCOME,
                {
                    "id": ev.new_id(ev.OUTCOME_PREFIX),
                    "about": receipt_id,
                    "verdict": verdict.value,
                    "source": OutcomeSource.REALITY.value,
                    "evidence": [ev.new_id()],
                    "by": None,
                    "note": "synthetic settlement",
                    "latency_s": 3600.0,
                    "ts": end.isoformat(),
                },
            )
            for receipt_id, verdict in settled_receipts
        ]
    )
    node.store.append("requests", rows)
    return target


def _receipt_body(
    did: str,
    receipt_id: str,
    schema: str,
    tier: Tier,
    cost: float,
    stamp: datetime,
    key: str,
    i: int,
) -> dict[str, Any]:
    return {
        "id": receipt_id,
        "caller": "user:synthetic",
        "request_hash": ev.sha256({"schema": schema, "i": i}),
        "response_hash": ev.sha256({"schema": schema, "answer": i}),
        "scope_result": "in_scope",
        "reason": None,
        "tier_used": tier.value,
        "determinism": "derived" if tier is Tier.T0 else "attested",
        "model_version": "frontier:local:synthetic" if tier is not Tier.T0 else "rule:synthetic",
        "citations": [ev.new_id()],
        "upstream": [],
        "hops": [did],
        "settle_key": key,
        "cost_credits": cost,
        "price_credits": cost * 1.5,
        "ts": stamp.isoformat(),
    }


def _request_row(
    receipt_id: str,
    schema: str,
    tier: Tier,
    cost: float,
    stamp: datetime,
    question: str,
    key: str,
    i: int,
) -> dict[str, Any]:
    return RequestRecord(
        id=ev.new_id(ev.REQUEST_PREFIX),
        ts=stamp.isoformat(),
        question=question,
        shape=f"what is {schema.split('.')[0]} #",
        caller="user:synthetic",
        scope_result="in_scope",
        reason=None,
        decided_by=f"tier:{tier.value}",
        tier_used=tier.value,
        tiers_tried=[tier.value],
        determinism="derived" if tier is Tier.T0 else "attested",
        schemas=[schema],
        tools=[],
        answer_shape="{answer}",
        citations=[],
        citations_n=1,
        latency_ms=12.0,
        cost_credits=cost,
        price_credits=cost * 1.5,
        receipt_id=receipt_id,
        settle_key=key,
        request_hash=ev.sha256({"schema": schema, "i": i}),
        response_hash=ev.sha256({"schema": schema, "answer": i}),
    ).as_row()


def node_with_events(tmp_path: Path | str, *, name: str = "cell", scope: str = "notes") -> Path:
    """The template's starter cell with its own fixtures ingested. The common base."""
    target = Path(tmp_path) / name
    node_mod.init(target, scope=scope)
    node_mod.open_node(target).ingest(target / "fixtures" / "events.jsonl")
    return target


def note_check(node_dir: Path | str, topic: str, verdict: str, *, minutes_ago: int = 5) -> Path:
    """A settling fact for the template's `note.v1`, dated in the past so the gate takes it."""
    stamp = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    path = Path(node_dir) / f"check-{topic}-{verdict}.jsonl"
    path.write_text(
        json.dumps({"schema_ref": "note_check.v1", "topic": topic, "verdict": verdict, "ts": stamp})
        + "\n",
        encoding="utf-8",
    )
    return path


FIXTURES = Path(__file__).resolve().parents[2] / "evals" / "gate_fixtures"


@dataclass
class Peer:
    """A cell that can ask other cells and learn from what comes back.

    `ask` is what any caller does: send the question with its own did and hop list, then
    adopt whatever route hints the answer carried. That second step is the whole mechanism
    by which the network finds short paths (KNP-1 section 5.2).
    """

    dir: Path
    did: str

    def ask(self, target: Peer, question: str, *, hops: list[str] | None = None) -> Any:
        from kourob import serve
        from kourob.routes import RouteTable

        answer = serve.answer(
            node_mod.open_node(target.dir), question, caller=self.did, hops=list(hops or [])
        )
        if answer.route_hints:
            RouteTable.load(self.dir).learn(answer.route_hints)
        return answer


def tennis_cell(tmp_path: Path | str, *, name: str = "tennis") -> Path:
    """A cell owning shot.v1, with the gate fixtures ingested and the lookup rule installed."""
    import shutil

    target = Path(tmp_path) / name
    node = node_mod.init(target, scope="tennis shot events for charted matches")
    shutil.copy(FIXTURES / "schema.odcs.yaml", target / "schemas" / "shot.odcs.yaml")
    shutil.copy(
        FIXTURES / "rules" / "shot-lookup.yaml",
        target / "tiers" / "t0" / "rules" / "shot-lookup.yaml",
    )
    node.manifest.scope.schemas = ["shot.v1", "note.v1", "note_check.v1"]
    manifest_mod.save(target, node.manifest)
    node_mod.open_node(target).ingest(FIXTURES / "events.jsonl")
    return target


def two_node_fixture(tmp_path: Path | str, *, bridge_limit: int = 3) -> tuple[Peer, Peer, Peer]:
    """kourob-node, tennis-node, and a caller connected only to kourob-node.

    kourob-node declares tennis out of scope and names tennis-node; the caller does not know
    tennis-node exists. That is exactly the situation a bridge is for.
    """
    base = Path(tmp_path)
    tennis_dir = tennis_cell(base)
    tennis = node_mod.open_node(tennis_dir)

    kourob_dir = node_with_events(base, name="kourob-node", scope="the KouroB design, as notes")
    kourob = node_mod.open_node(kourob_dir)
    kourob.manifest.scope.excludes = [
        manifest_mod.Exclusion(pattern=r"tennis|shot|match|serve|rally", refer_to=tennis.did)
    ]
    kourob.manifest.bridge.bridge_limit = bridge_limit
    manifest_mod.save(kourob_dir, kourob.manifest)
    node_mod.connect(node_mod.open_node(kourob_dir), tennis_dir)

    caller_dir = node_with_events(base, name="caller", scope="a caller that only knows kourob-node")
    node_mod.connect(node_mod.open_node(caller_dir), kourob_dir)

    return (
        Peer(kourob_dir, kourob.did),
        Peer(tennis_dir, tennis.did),
        Peer(caller_dir, node_mod.open_node(caller_dir).did),
    )


__all__ = [
    "Peer",
    "node_with_events",
    "note_check",
    "synthetic_request_log",
    "tennis_cell",
    "two_node_fixture",
]
