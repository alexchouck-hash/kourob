"""shadow: the node's own T3 audits a budgeted sample of what its cheap tiers said.

Specified in ADR-0011. Builds on ADR-0007 (outcomes) and ADR-0010 (settle keys).

Reality settles only answers whose subject a later fact names, and only when that fact
arrives. Everything else a cheap tier says goes unchecked, and those unchecked answers are
exactly where a promoted rule or a student can be quietly wrong. This loop asks the teacher
the same question off the hot path and compares what the two cited.

The asymmetry is the design. ADR-0007 rejected tier agreement as a label because it cannot
catch a mistake both tiers make, so **agreement is not recorded as an outcome**. It only
makes the next audit in that cluster less likely. **Disagreement is recorded**: one of the
two is wrong, and the node should not make that cluster cheaper until reality or a human
says which. A dispute goes on the chain as `source: teacher`, which settles nothing and
trains nothing (`ledger.outcomes.settling_outcomes`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob.ledger.outcome import OutcomeSource, Verdict
from kourob.ledger.outcomes import settling_outcomes, submit
from kourob.loops.clustering import cluster_key
from kourob.request_log import RequestRecord
from kourob.runner.run import Runner
from kourob.tiers.base import Request
from kourob.tiers.t3_frontier import T3Frontier
from kourob.types import Tier

__milestone__ = "M4"

SHADOW_TABLE = "shadow"
#: The tiers worth auditing. T3 is the teacher, so it cannot audit itself. T4 is a human.
AUDITED_TIERS = frozenset({Tier.T0.value, Tier.T1.value, Tier.T2.value})
#: However long a cluster has agreed, one answer in twenty is still checked. A rule that is
#: right a thousand times can still go wrong when the data under it changes.
MIN_RATE = 0.05
DEFAULT_BUDGET = 0.5
TEACHER = "teacher:shadow"

AGREE = "agree"
DISPUTE = "dispute"
ABSTAIN = "abstain"


def sample_rate(agreed_since_dispute: int) -> float:
    """1, 1/2, 1/3, ..., floored at `MIN_RATE`.

    The expected number of audits grows with the log of a cluster's volume rather than the
    volume itself, so the teacher's cost shrinks per answer as a cluster earns trust. A
    dispute resets the count to zero and every answer is checked again.
    """
    return max(MIN_RATE, 1.0 / (1 + agreed_since_dispute))


def _draw(receipt_id: str) -> float:
    """A uniform draw fixed by the receipt, so a rerun samples the same answers."""
    digest = hashlib.sha256(receipt_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass
class Audit:
    id: str
    receipt_id: str
    cluster: str
    tier: str
    verdict: str
    rate: float
    answer_citations: list[str]
    teacher_citations: list[str]
    teacher_model: str
    cost_credits: float
    outcome_id: str | None
    ts: str

    def as_row(self) -> dict[str, Any]:
        row = self.__dict__.copy()
        row["answer_citations"] = ",".join(self.answer_citations)
        row["teacher_citations"] = ",".join(self.teacher_citations)
        return row


@dataclass
class ShadowReport:
    budget_credits: float
    considered: int = 0
    spent_credits: float = 0.0
    exhausted: bool = False
    #: No teacher to ask. Nothing is recorded, so every answer is still owed an audit.
    unavailable: bool = False
    audits: list[Audit] = field(default_factory=list)

    def count(self, verdict: str) -> int:
        return sum(1 for a in self.audits if a.verdict == verdict)

    def __str__(self) -> str:
        if self.unavailable and not self.audits:
            return "shadow: the teacher (T3) is unreachable, so nothing was audited"
        stop = ", budget exhausted" if self.exhausted else ""
        stop += ", teacher became unreachable" if self.unavailable else ""
        return (
            f"shadow: {len(self.audits)} audited of {self.considered} unsettled cheap-tier "
            f"answers - {self.count(AGREE)} agree, {self.count(DISPUTE)} dispute, "
            f"{self.count(ABSTAIN)} abstain; spent {self.spent_credits:.6f} of "
            f"{self.budget_credits:.6f} credits{stop}"
        )


def run_shadow(
    node_dir: Path | str,
    *,
    runner: Runner | None = None,
    budget_credits: float | None = None,
    now: datetime | None = None,
) -> ShadowReport:
    """Audit what the budget allows, oldest unsettled answer first. Returns what it did."""
    from kourob.node import open_node

    node = open_node(node_dir)
    config = node.manifest.loops.get("shadow") or {}
    if budget_credits is None:
        budget_credits = float(config.get("budget_credits", DEFAULT_BUDGET))
    budget = float(budget_credits)
    report = ShadowReport(budget_credits=budget)
    if node.store.stats("requests")["rows"] == 0:
        return report

    has_prior = node.store.stats(SHADOW_TABLE)["rows"] > 0
    prior = node.store.scan(SHADOW_TABLE, order_by="id") if has_prior else []
    audited = {str(r["receipt_id"]) for r in prior}
    agreed: dict[str, int] = {}
    for row in prior:
        _tally(agreed, str(row["cluster"]), str(row["verdict"]))
    settled = {o.about for o in settling_outcomes(node.ledger)}

    teacher = T3Frontier(
        node.dir,
        node.store,
        runner or Runner(node.manifest, store=node.store),
        node.manifest,
        purpose="shadow",
    )
    if not teacher.available():
        report.unavailable = True
        return report
    bar = node.manifest.confidence_bar(Tier.T3)

    for raw in node.store.scan("requests", order_by="id"):
        record = RequestRecord.from_row(raw)
        receipt_id = str(record.get("receipt_id") or "")
        if (
            record.get("scope_result") != "in_scope"
            or record.get("tier_used") not in AUDITED_TIERS
            or not record.get("citations")
            or receipt_id in audited
            or receipt_id in settled
        ):
            continue
        report.considered += 1
        cluster = cluster_key(record)
        rate = sample_rate(agreed.get(cluster, 0))
        if _draw(receipt_id) >= rate:
            continue
        if report.spent_credits >= budget:
            report.exhausted = True
            break

        result = teacher.attempt(Request(question=str(record["question"]), caller=TEACHER))
        if result.detail.startswith("adapter unavailable"):
            # A teacher that cannot be reached has not abstained. Recording it would mark
            # the answer audited and it would never be checked again.
            report.unavailable = True
            break
        report.spent_credits += result.cost_credits
        answer_cited = sorted(record["citations"])
        teacher_cited = sorted(result.citations) if result.answered else []

        outcome_id: str | None = None
        if not result.answered or result.confidence < bar or not teacher_cited:
            verdict = ABSTAIN
        elif set(answer_cited) & set(teacher_cited):
            verdict = AGREE
        else:
            verdict = DISPUTE
            outcome = submit(
                node.ledger,
                receipt_id,
                verdict=Verdict.REJECTED,
                source=OutcomeSource.TEACHER,
                evidence=teacher_cited,
                note=(
                    f"{result.model_version} answering the same question cited "
                    f"{', '.join(teacher_cited)}; the {record['tier_used']} answer cited "
                    f"{', '.join(answer_cited)}"
                ),
                now=now,
            )
            outcome_id = outcome.id

        report.audits.append(
            Audit(
                id=ev.new_id("shd_"),
                receipt_id=receipt_id,
                cluster=cluster,
                tier=str(record["tier_used"]),
                verdict=verdict,
                rate=rate,
                answer_citations=answer_cited,
                teacher_citations=teacher_cited,
                teacher_model=result.model_version,
                cost_credits=result.cost_credits,
                outcome_id=outcome_id,
                ts=(now or ev.now()).isoformat(),
            )
        )
        audited.add(receipt_id)
        _tally(agreed, cluster, verdict)

    if report.audits:
        node.store.append(SHADOW_TABLE, [a.as_row() for a in report.audits])
    return report


def _tally(agreed: dict[str, int], cluster: str, verdict: str) -> None:
    if verdict == AGREE:
        agreed[cluster] = agreed.get(cluster, 0) + 1
    elif verdict == DISPUTE:
        agreed[cluster] = 0


def disputed_receipts(node: Any) -> set[str]:
    """Receipts the teacher disputed and nothing has settled since. Reality overrides it."""
    from kourob.ledger.outcomes import read_outcomes

    outcomes = read_outcomes(node.ledger)
    settled = {o.about for o in outcomes if o.source is not OutcomeSource.TEACHER}
    return {
        o.about for o in outcomes if o.source is OutcomeSource.TEACHER and o.about not in settled
    }


__all__ = [
    "ABSTAIN",
    "AGREE",
    "DISPUTE",
    "MIN_RATE",
    "SHADOW_TABLE",
    "Audit",
    "ShadowReport",
    "disputed_receipts",
    "run_shadow",
    "sample_rate",
]
