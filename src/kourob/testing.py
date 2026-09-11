"""Fixtures the evals and tests build nodes from.

Brief reference: DEFAULTS.md — no network in unit tests; model calls go through the
runner's `local` adapter.

These build **synthetic traffic**, not synthetic nodes: the manifest, gate, ledger and
store are the real ones, and only the demand is invented. A fixture that stubbed the node
would prove nothing about the node.
"""

from __future__ import annotations

import contextlib
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
    # A shot-charting cell does not predict winners. Declaring that (KNP-1 section 2) is
    # what makes "who wins wimbledon" a refusal here rather than a question T3 gets asked.
    node.manifest.scope.excludes = [
        manifest_mod.Exclusion(pattern=r"who wins|winner of|champion|prediction", refer_to=None)
    ]
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


def _scripted_grounded_runner(node: Any) -> Any:
    """A T3 stand-in that answers from the events it is shown, citing the right one.

    Parses the numbered events out of the prompt and returns the body of the one whose topic
    the question names — or the first event when nothing matches, which is how an
    edge-case question still gets a grounded, settleable answer.
    """
    from kourob.runner import Runner
    from kourob.runner.adapters import LocalAdapter

    def reply(prompt: str) -> str:
        from kourob.loops.distill.mine import subject_of

        question = prompt.rsplit("Question:", 1)[-1].strip()
        subject = subject_of(question)
        events: list[tuple[str, dict[str, Any]]] = []
        for line in prompt.splitlines():
            line = line.strip()
            if line.startswith("evt_") and "(" in line:
                event_id, rest = line.split(None, 1)
                payload = json.loads(rest.split(")", 1)[1].strip())
                events.append((event_id, payload))
        chosen = next(
            ((i, p) for i, p in events if str(p.get("topic", "")).lower() == subject),
            events[0] if events else (None, {}),
        )
        event_id, payload = chosen
        return json.dumps(
            {
                "answer": payload.get("body", "no body"),
                "citations": [event_id] if event_id else [],
                "confidence": 0.9,
            }
        )

    return Runner(
        node.manifest,
        store=node.store,
        adapters={"local": LocalAdapter.scripted([], fallback=reply)},
    )


def t3_answered_cell(
    tmp_path: Path | str, *, topics: int = 8, edge: bool = False, n_rule: int = 5
) -> Path:
    """A cell whose settled answers all came from T3 and were all a function of one note.

    The template's hand-written rule is disabled so the model has to answer; every answer is
    then settled `accepted` from reality. This is the raw material rule mining works on.
    """
    from kourob import serve
    from kourob.ledger.outcome import OutcomeSource, Verdict
    from kourob.ledger.outcomes import submit
    from kourob.tiers.t0_rules import RULES_DIR

    target = Path(tmp_path) / "t3cell"
    node = node_mod.init(target, scope="the KouroB design, as notes")
    for rule in (target / RULES_DIR).glob("*.yaml"):
        rule.rename(rule.with_suffix(".yaml.disabled"))
    node.manifest.loops["evolve"] = {"n_rule": n_rule}
    manifest_mod.save(target, node.manifest)

    stamp = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    notes = target / "notes.jsonl"
    notes.write_text(
        "".join(
            json.dumps(
                {
                    "schema_ref": "note.v1",
                    "topic": f"topic-{i}",
                    "body": f"Topic {i} is the {i}th thing this cell knows about, at length.",
                    "ts": stamp,
                }
            )
            + "\n"
            for i in range(topics)
        ),
        encoding="utf-8",
    )
    node_mod.open_node(target).ingest(notes)

    questions = [f"what is topic-{i}" for i in range(topics)]
    if edge:
        questions.append("what is the mechanism")
    for question in questions:
        node = node_mod.open_node(target)
        answer = serve.answer(node, question, runner=_scripted_grounded_runner(node))
        assert answer.tier_used is not None, f"{question!r} was not answered: {answer.rendered}"
        submit(
            node_mod.open_node(target).ledger,
            answer.receipt_id,
            verdict=Verdict.ACCEPTED,
            source=OutcomeSource.REALITY,
            evidence=list(answer.citations),
        )
    return target


def cluster_with_an_edge_case(tmp_path: Path | str) -> tuple[Any, Any, dict[str, Any]]:
    """(store, cluster, verdicts) for a function-of-one-note cluster with one question the
    mined rule cannot bind. Twenty it can, one it cannot: coverage 0.952."""
    from kourob.ledger.outcomes import read_outcomes
    from kourob.loops.clustering import REFUSED, build_clusters

    target = t3_answered_cell(tmp_path, topics=20, edge=True)
    node = node_mod.open_node(target)
    verdicts = {o.about: o.verdict for o in read_outcomes(node.ledger)}
    clusters = build_clusters(
        node.store.scan("requests", order_by="id"), outcomes_by_receipt=verdicts
    )
    (cluster,) = [c for c in clusters if not c.key.startswith(REFUSED)]
    return node.store, cluster, verdicts


def node_with_promoted_rule(tmp_path: Path | str) -> tuple[Path, str]:
    """A cell where evolve mined a rule, the rule was installed, and T0 has answered with it."""
    from kourob import serve
    from kourob.loops.evolve import ProposalKind, evolve
    from kourob.tiers.t0_rules import RULES_DIR

    target = t3_answered_cell(tmp_path, topics=8)
    report = evolve(target)
    (promotion,) = [p for p in report.proposals if p.kind is ProposalKind.PROMOTE]
    rule_id = str(promotion.evidence["rule"])
    (Path(target) / RULES_DIR / f"{rule_id}.yaml").write_text(
        str(promotion.evidence["rule_yaml"]), encoding="utf-8"
    )
    answer = serve.answer(node_mod.open_node(target), "what is topic-1")
    assert answer.tier_used is Tier.T0, f"the mined rule did not answer: {answer.rendered}"
    return target, rule_id


def correct_one_t0_answer(node_dir: Path | str, rule_id: str) -> str:
    """Settle the latest answer the rule gave as `corrected`. Returns the outcome id."""
    from kourob.ledger.outcome import OutcomeSource, Verdict
    from kourob.ledger.outcomes import submit

    node = node_mod.open_node(node_dir)
    receipt = next(
        r
        for r in reversed(node.ledger.records())
        if r.get("kind", "receipt") == "receipt" and r.get("model_version") == f"rule:{rule_id}"
    )
    return submit(
        node.ledger,
        receipt["id"],
        verdict=Verdict.CORRECTED,
        source=OutcomeSource.REALITY,
        evidence=[ev.new_id()],
        note="the rule was wrong once, which is once too many",
    ).id


def outcomes_for_tier(node_dir: Path | str, tier: Tier) -> list[Any]:
    from kourob.ledger.outcomes import read_outcomes

    node = node_mod.open_node(node_dir)
    tiered = {r["id"] for r in node.ledger.records() if r.get("tier_used") == tier.value}
    return [o for o in read_outcomes(node.ledger) if o.about in tiered]


@dataclass
class DayStats:
    """One day of replayed traffic, as the cost-curve eval reads it."""

    day: int
    requests: int
    cost_per_request: float
    tier_share: dict[str, float]


def _shot_questions() -> list[tuple[str, bool]]:
    """(question, t0_bindable) over the accepted gate fixtures, in two phrasings."""
    import json

    rows = [
        json.loads(line)
        for line in (FIXTURES / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("_expect") == "accept"
    ]
    out: list[tuple[str, bool]] = []
    for row in rows:
        m, p, i = row["match_id"], row["point_id"], row["shot_index"]
        out.append((f"shot {i} of point {p} in match {m}", True))
        out.append((f"which player hit shot {i} in point {p} of match {m}", False))
    return out


def tennis_node_fixture(tmp_path: Path | str, *, with_gold: bool = True) -> Path:
    """The tennis cell, with a gold set labelled by what the node's own rule path decides.

    Gold here is honest in the only way a synthetic gold can be: the labels are the teacher's
    decisions on questions the teacher has not otherwise seen, so a student that matches
    them has learned the decision boundary rather than memorised the training rows.
    """
    import json

    from kourob.loops.distill.calibrate import teacher_label

    cell = tennis_cell(tmp_path, name="tennis-node")
    node = node_mod.open_node(cell)
    node.manifest.pricing.token_rates.pop("local", None)  # price local model calls for real
    manifest_mod.save(cell, node.manifest)
    if with_gold:
        node = node_mod.open_node(cell)
        questions = [q for q, _ in _shot_questions()] + [
            "who wins wimbledon",
            "who wins the french open",
            "how did the tennis match go",
        ]
        lines = [json.dumps({"question": q, "label": teacher_label(node, q)}) for q in questions]
        node.gate.ingest_gold(lines, task="scope_classifier")
        _warm_student(cell)
    return cell


def _warm_student(cell: Path) -> None:
    """Ask, settle, and enable: the student needs settled answers to learn from.

    Two passes over the shot questions through the real serving path with a scripted
    grounded model, every accepted answer settled as `source: reality`, then `enable` -
    which trains on those, calibrates on gold, and switches T1 on.
    """
    from kourob import serve
    from kourob.ledger.chain import RECORD_OUTCOME
    from kourob.tiers.t1_student import T1Student

    node = node_mod.open_node(cell)
    runner = _scripted_grounded_runner(node)
    settle: list[tuple[str, dict[str, Any]]] = []
    for _ in range(2):
        for question, _bindable in _shot_questions():
            answer = serve.answer(node, question, caller="user:warm", runner=runner)
            if answer.scope_result.value == "in_scope" and answer.citations:
                settle.append(
                    (
                        RECORD_OUTCOME,
                        {
                            "id": ev.new_id(ev.OUTCOME_PREFIX),
                            "about": answer.receipt_id,
                            "verdict": "accepted",
                            "source": "reality",
                            "evidence": list(answer.citations[:1]),
                            "by": None,
                            "note": "warm-up settlement",
                            "latency_s": 60.0,
                            "ts": ev.now().isoformat(),
                        },
                    )
                )
    node.ledger.extend(settle)
    T1Student.enable(node_mod.open_node(cell))


def replay_synthetic_traffic(
    node_dir: Path | str,
    *,
    days: int = 30,
    requests_per_day: int = 200,
    evolve_weekly: bool = True,
    t3_share: float = 0.3,
) -> list[DayStats]:
    """Thirty days of a cell's life, compressed: ask, settle, tend weekly, measure.

    Each day asks `requests_per_day` questions - a mix of rule-bindable lookups and
    paraphrases only a model answers - through the real serving path with a scripted
    grounded model priced at the default token rate. Every accepted answer is settled that
    day (`source: reality`), so the promotion gates see what a real settled cell would.
    Weekly, `tend` runs at A2 and applies what it may. Cost per request is measured from
    the request log, not computed from the tiers.
    """
    import random

    from kourob import serve
    from kourob.ledger.chain import RECORD_OUTCOME
    from kourob.loops.tend import tend
    from kourob.tiers.t1_student import T1Student

    node_dir = Path(node_dir)
    node = node_mod.open_node(node_dir)
    node.manifest.autonomy.level = "A2"  # type: ignore[assignment]
    manifest_mod.save(node_dir, node.manifest)
    # A caller that asks two hundred times a day for a month is a paying caller. The first
    # replay forgot this: the free allowance ran out on day one and every request after
    # was refused for credit - the curve measured a node saying no, at no cost.
    from kourob.ledger.accounts import Accounts

    Accounts(node.store).credit("user:replay", 1_000.0, note="replay: a month of a paying caller")
    # Day one is a node that has not distilled anything yet. The fixture's warm-up enabled
    # T1 so the student could be scored; the replay switches it off and lets the weekly
    # tend bring it back, so the curve starts where a real cell starts.
    T1Student.disable(node)

    rng = random.Random(7)
    lookups = [q for q, bindable in _shot_questions() if bindable]
    paraphrases = [q for q, bindable in _shot_questions() if not bindable]
    stats: list[DayStats] = []

    for day in range(1, days + 1):
        node = node_mod.open_node(node_dir)
        runner = _scripted_grounded_runner(node)
        costs: list[float] = []
        tiers: dict[str, int] = {}
        settle: list[tuple[str, dict]] = []
        for _ in range(requests_per_day):
            question = rng.choice(paraphrases if rng.random() < t3_share else lookups)
            answer = serve.answer(node, question, caller="user:replay", runner=runner)
            row = node.store.query(
                "SELECT cost_credits, tier_used FROM requests WHERE receipt_id = $r",
                {"r": answer.receipt_id},
            ).to_pylist()[0]
            costs.append(float(row["cost_credits"] or 0.0))
            tier = str(row["tier_used"] or "-")
            tiers[tier] = tiers.get(tier, 0) + 1
            if answer.scope_result.value == "in_scope" and answer.citations:
                settle.append(
                    (
                        RECORD_OUTCOME,
                        {
                            "id": ev.new_id(ev.OUTCOME_PREFIX),
                            "about": answer.receipt_id,
                            "verdict": "accepted",
                            "source": "reality",
                            "evidence": list(answer.citations[:1]),
                            "by": None,
                            "note": f"replay day {day}",
                            "latency_s": 3600.0,
                            "ts": ev.now().isoformat(),
                        },
                    )
                )
        node.ledger.extend(settle)  # the store folds its own parts as they pile up

        if evolve_weekly and day % 7 == 0:
            tend(node_dir, autonomy_max="A2", budget=10.0)
            fresh = node_mod.open_node(node_dir)
            if not fresh.manifest.tier_enabled(Tier.T1):
                # The operator's move, once there is something to check it against: enable
                # the student. Its bar is calibrated on gold, per class, as it is enabled.
                with contextlib.suppress(ValueError):  # no gold yet: T3 keeps serving
                    T1Student.enable(fresh)

        total = max(1, len(costs))
        stats.append(
            DayStats(
                day=day,
                requests=len(costs),
                cost_per_request=sum(costs) / total,
                tier_share={t: n / total for t, n in tiers.items()}
                | {t: 0.0 for t in ("T0", "T1", "T3") if t not in tiers},
            )
        )
    return stats


__all__ = [
    "DayStats",
    "Peer",
    "cluster_with_an_edge_case",
    "correct_one_t0_answer",
    "node_with_events",
    "node_with_promoted_rule",
    "note_check",
    "outcomes_for_tier",
    "replay_synthetic_traffic",
    "synthetic_request_log",
    "t3_answered_cell",
    "tennis_cell",
    "tennis_node_fixture",
    "two_node_fixture",
]
