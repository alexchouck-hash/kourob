"""`kourob tend`: the self-development cycle. Decide, apply within autonomy, propose the rest.

Brief reference: KNP-7 sections 2, 4 and 5.

    ingest -> evolve -> decide -> apply | propose -> report

`decide` is the only new step over `evolve`. For each proposal it asks three questions in
order, and any "no" turns an apply into a propose:

1. Is this within the node's autonomy level?
2. Does the budget cover it?
3. Is it reversible — is there a recorded inverse `rollback` can apply?

Question 3 does the real work. **A change with no recorded inverse is never auto-applied,
at any level.** Every applied change is a `node_change.v1` event pushed through the gate
like any other fact, carrying its inverse, so the node can explain not just what it answered
but why it is the shape it is.

Halt conditions stop the cycle, apply nothing further, and demote the node one autonomy
level. A node cannot promote itself: graduation is *suggested* here and decided by whoever
runs the set.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from kourob import events as ev
from kourob import manifest as manifest_mod
from kourob.loops.evolve import EvolveReport, Proposal, ProposalKind, evolve
from kourob.node import Node, open_node
from kourob.tiers.t0_rules import RULES_DIR

__milestone__ = "M4"

LEVELS = ("A0", "A1", "A2", "A3", "A4")
REPORT_DIR = "logs/tend"
CHANGE_SCHEMA = "node_change.v1"

#: The autonomy level each proposal kind needs before it may be applied without asking
#: (KNP-7 section 2). Kinds absent here are always proposals: a split creates a cell, and
#: scope changes need a human at every level (KNP-7 section 1).
REQUIRED_LEVEL: dict[ProposalKind, str] = {
    ProposalKind.PROMOTE: "A2",
    ProposalKind.DEMOTE: "A2",
    ProposalKind.SHED: "A3",
}

MIN_RECEIPTS_FOR_SETTLE_HALT = 20


class TendError(RuntimeError):
    pass


@dataclass
class Decision:
    proposal: Proposal
    action: str  # apply | propose | halt
    why: str
    cost: float = 0.0


class Applied(BaseModel):
    event_id: str
    kind: str
    target: str
    inverse: dict[str, Any]


class TendReport(BaseModel):
    node: str
    ts: datetime
    level: str
    effective_level: str
    budget: float
    spent: float = 0.0
    ingested: int = 0
    applied: list[Applied] = Field(default_factory=list)
    proposed: list[Proposal] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None
    demoted_to: str | None = None
    graduation_suggested: str | None = None
    dry_run: bool = False
    evolve: EvolveReport | None = None


# --------------------------------------------------------------------------------- levels


def level_index(level: str) -> int:
    if level not in LEVELS:
        raise TendError(f"unknown autonomy level {level!r}; expected one of {LEVELS}")
    return LEVELS.index(level)


def _effective(node: Node, autonomy_max: str) -> str:
    return LEVELS[min(level_index(node.manifest.autonomy.level), level_index(autonomy_max))]


def _set_level(node: Node, level: str) -> None:
    node.manifest.autonomy.level = level  # type: ignore[assignment]
    manifest_mod.save(node.dir, node.manifest)


# --------------------------------------------------------------------------- changes


def record_change(
    node: Node,
    *,
    kind: str,
    target: str,
    level: str,
    inverse: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    reverts: str | None = None,
    cost: float = 0.0,
) -> str:
    """Push a node_change.v1 event through the gate. Returns the event id.

    Through the gate, not around it: the gate is the only silver writer (AGENTS.md
    section 4), and a change the node made to itself is a fact like any other.
    """
    payload = {
        "schema_ref": CHANGE_SCHEMA,
        "kind": kind,
        "target": target,
        "autonomy_level": level,
        "evidence": json.dumps(evidence or {}, sort_keys=True, default=str),
        "inverse": json.dumps(inverse, sort_keys=True),
        "reverts": reverts,
        "cost_credits": cost,
        "ts": ev.now().isoformat(),
    }
    report = node.gate.ingest_lines([json.dumps(payload)], source="tend")
    if not report.event_ids:
        raise TendError(f"the gate refused to record a change: {report.reasons}")
    return report.event_ids[0]


def changes(node: Node) -> list[dict[str, Any]]:
    """Every change this node has made to itself, oldest first."""
    if node.store.stats("silver")["rows"] == 0:
        return []
    return [
        row
        for row in node.store.scan("silver", order_by="id")
        if row.get("schema_ref") == CHANGE_SCHEMA
    ]


def _rule_paths(node: Node, rule_id: str) -> tuple[Path, Path]:
    live = node.dir / RULES_DIR / f"{rule_id}.yaml"
    return live, live.with_suffix(".yaml.disabled")


def apply_change(node: Node, kind: str, target: str, *, rule_yaml: str | None = None) -> bool:
    """Perform one change or its inverse. Returns whether anything actually changed.

    Every branch here has a partner branch that undoes it, and nothing here deletes.
    A shed removes a declaration and leaves the data; a demote renames a rule file.
    """
    if kind == "promote":
        live, disabled = _rule_paths(node, target)
        if live.exists():
            return False
        if disabled.exists():
            disabled.rename(live)
            return True
        if rule_yaml is None:
            raise TendError(f"cannot enable {target}: no rule text and no disabled file")
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_text(rule_yaml, encoding="utf-8")
        return True
    if kind == "demote":
        live, disabled = _rule_paths(node, target)
        if not live.exists():
            return False
        live.rename(disabled)
        return True
    if kind == "shed":
        if target not in node.manifest.scope.schemas:
            return False
        node.manifest.scope.schemas.remove(target)
        manifest_mod.save(node.dir, node.manifest)
        return True
    if kind == "restore":
        if target in node.manifest.scope.schemas:
            return False
        node.manifest.scope.schemas.append(target)
        manifest_mod.save(node.dir, node.manifest)
        return True
    if kind == "autonomy":
        if node.manifest.autonomy.level == target:
            return False
        _set_level(node, target)
        return True
    raise TendError(f"no way to apply a change of kind {kind!r}")


def _inverse_of(proposal: Proposal) -> dict[str, Any] | None:
    """The recorded inverse for a proposal, or None — and None means never auto-apply."""
    if proposal.kind is ProposalKind.PROMOTE and proposal.to_tier is not None:
        rule = proposal.evidence.get("rule")
        return {"kind": "demote", "target": rule} if rule else None
    if proposal.kind is ProposalKind.DEMOTE:
        rule = proposal.evidence.get("rule")
        return {"kind": "promote", "target": rule} if rule else None
    if proposal.kind is ProposalKind.SHED:
        schema = proposal.evidence.get("schema")
        return {"kind": "restore", "target": schema} if schema else None
    return None


def _target_of(proposal: Proposal) -> str:
    return str(
        proposal.evidence.get("rule") or proposal.evidence.get("schema") or proposal.cluster or "?"
    )


# --------------------------------------------------------------------------------- halts


def _halt_reason(node: Node, evolve_report: EvolveReport) -> str | None:
    """KNP-7 section 4.2. Any of these means more autonomous change makes things worse."""
    from kourob.ledger.outcomes import settlement_status

    if not node.ledger.verify().ok:
        return "ledger verify failed: every piece of evidence here is now untrusted"

    status = settlement_status(node.ledger, node.contracts)
    q_floor = node.manifest.pricing.q_floor
    if status.settled > 0 and status.quality_multiplier() < q_floor:
        return (
            f"quality {status.quality_multiplier():.2f} below q_floor {q_floor}: "
            "the node is getting worse"
        )
    if (
        status.total >= MIN_RECEIPTS_FOR_SETTLE_HALT
        and status.settle_rate < node.manifest.autonomy.settle_floor
    ):
        return (
            f"settle_rate {status.settle_rate:.2f} below settle_floor "
            f"{node.manifest.autonomy.settle_floor}: nothing can be verified"
        )

    recent = [c.get("payload", {}).get("kind") for c in changes(node)[-2:]]
    if len(recent) == 2 and all(k == "rollback" for k in recent):
        return "two consecutive rollbacks: the evidence gates themselves are suspect"
    return None


# --------------------------------------------------------------------------------- decide


def decide(node: Node, proposals: list[Proposal], *, level: str, budget: float) -> list[Decision]:
    decisions: list[Decision] = []
    remaining = budget
    for proposal in proposals:
        required = REQUIRED_LEVEL.get(proposal.kind)
        if required is None:
            decisions.append(
                Decision(proposal, "propose", f"{proposal.kind.value} always needs a human")
            )
            continue
        if level_index(level) < level_index(required):
            decisions.append(Decision(proposal, "propose", f"needs {required}, node is at {level}"))
            continue
        cost = float(proposal.evidence.get("cost_credits", 0.0) or 0.0)
        if cost > remaining:
            decisions.append(
                Decision(proposal, "propose", f"costs {cost:.4f}, budget has {remaining:.4f}")
            )
            continue
        if _inverse_of(proposal) is None:
            decisions.append(
                Decision(proposal, "propose", "no recorded inverse: never auto-applied")
            )
            continue
        remaining -= cost
        decisions.append(Decision(proposal, "apply", f"within {level}, reversible", cost=cost))
    return decisions


# ---------------------------------------------------------------------------------- tend


def tend(
    node_dir: Path | str,
    *,
    budget: float = 1.0,
    autonomy_max: str = "A4",
    dry_run: bool = False,
    now: datetime | None = None,
) -> TendReport:
    node = open_node(node_dir)
    level = _effective(node, autonomy_max)
    report = TendReport(
        node=node.did,
        ts=now or ev.now(),
        level=node.manifest.autonomy.level,
        effective_level=level,
        budget=budget,
        dry_run=dry_run,
    )

    report.ingested = _ingest_inbox(node)
    report.evolve = evolve(node.dir, now=now)
    node = open_node(node_dir)  # evolve may have disabled a rule; reload

    halt = _halt_reason(node, report.evolve)
    if halt is not None:
        report.halted = True
        report.halt_reason = halt
        report.proposed = list(report.evolve.proposals)
        if not dry_run:
            report.demoted_to = _demote(node, halt)
        _write_report(node.dir, report)
        return report

    decisions = decide(node, report.evolve.proposals, level=level, budget=budget)
    for decision in decisions:
        report.decisions.append(
            {"kind": decision.proposal.kind.value, "action": decision.action, "why": decision.why}
        )
        if decision.action != "apply":
            report.proposed.append(decision.proposal)
            continue
        if dry_run:
            continue
        applied = _apply(node, decision, level)
        if applied is not None:
            report.applied.append(applied)
            report.spent += decision.cost

    report.graduation_suggested = _graduation(node, report)
    _write_report(node.dir, report)
    return report


def _apply(node: Node, decision: Decision, level: str) -> Applied | None:
    proposal = decision.proposal
    inverse = _inverse_of(proposal)
    assert inverse is not None
    target = _target_of(proposal)
    kind = proposal.kind.value

    if proposal.kind is ProposalKind.DEMOTE and proposal.evidence.get("disabled"):
        changed = True  # evolve already renamed the file; this records the fact
    else:
        changed = apply_change(node, kind, target, rule_yaml=proposal.evidence.get("rule_yaml"))
    if not changed:
        return None
    event_id = record_change(
        node,
        kind=kind,
        target=target,
        level=level,
        inverse=inverse,
        evidence={k: v for k, v in proposal.evidence.items() if k != "rule_yaml"},
        cost=decision.cost,
    )
    return Applied(event_id=event_id, kind=kind, target=target, inverse=inverse)


def _demote(node: Node, why: str) -> str | None:
    """One level down, immediately, recorded with its inverse (KNP-7 section 2.2)."""
    current = node.manifest.autonomy.level
    if current == "A0":
        return None
    lower = LEVELS[level_index(current) - 1]
    apply_change(node, "autonomy", lower)
    record_change(
        node,
        kind="autonomy",
        target=lower,
        level=current,
        inverse={"kind": "autonomy", "target": current},
        evidence={"why": why},
    )
    return lower


def _graduation(node: Node, report: TendReport) -> str | None:
    """Suggest the next level after `graduation_window` clean cycles. Suggest, not set."""
    window = node.manifest.autonomy.graduation_window
    past = past_reports(node.dir)[-(window - 1) :] if window > 1 else []
    clean = [r for r in past if not r.get("halted")] + ([] if report.halted else [report])
    if len(clean) < window:
        return None
    if any(c.get("payload", {}).get("kind") == "rollback" for c in changes(node)[-window:]):
        return None
    current = node.manifest.autonomy.level
    if current == LEVELS[-1]:
        return None
    return LEVELS[level_index(current) + 1]


def _ingest_inbox(node: Node) -> int:
    inbox = node.dir / "data" / "bronze" / "inbox"
    if not inbox.exists():
        return 0
    accepted = 0
    for path in sorted(inbox.glob("*.jsonl")):
        result, _ = open_node(node.dir).ingest(path)
        accepted += result.accepted
        path.rename(path.with_suffix(".jsonl.done"))
    return accepted


# ------------------------------------------------------------------------------- rollback


def rollback(node_dir: Path | str, change_event_id: str) -> str:
    """Apply the recorded inverse of a change. Returns the rollback change's event id.

    A lookup, not a reconstruction: the inverse was written when the change was made, by
    the code that made it, and nothing here has to work out what undoing means.
    """
    node = open_node(node_dir)
    event = node.store.get("silver", change_event_id)
    if event is None or event.get("schema_ref") != CHANGE_SCHEMA:
        raise TendError(f"{change_event_id} is not a change this node made")
    payload = event.get("payload") or {}
    inverse = json.loads(payload.get("inverse") or "{}")
    if not inverse.get("kind") or not inverse.get("target"):
        raise TendError(f"{change_event_id} recorded no inverse and cannot be rolled back")

    apply_change(node, str(inverse["kind"]), str(inverse["target"]))
    return record_change(
        open_node(node_dir),
        kind="rollback",
        target=str(inverse["target"]),
        level=node.manifest.autonomy.level,
        inverse={"kind": str(payload.get("kind")), "target": str(payload.get("target"))},
        reverts=change_event_id,
        evidence={"undid": payload.get("kind")},
    )


# -------------------------------------------------------------------------------- reports


def past_reports(node_dir: Path | str) -> list[dict[str, Any]]:
    directory = Path(node_dir) / REPORT_DIR
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out


def _write_report(node_dir: Path | str, report: TendReport) -> Path:
    directory = Path(node_dir) / REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{report.ts.strftime('%Y%m%dT%H%M%S%f')}.json"
    path.write_text(report.model_dump_json(indent=2, exclude={"evolve"}), encoding="utf-8")
    return path


def render(report: TendReport) -> str:
    lines = [
        f"tend {report.ts:%Y-%m-%d %H:%M}  level {report.level} "
        f"(effective {report.effective_level})" + ("  DRY RUN" if report.dry_run else ""),
    ]
    if report.ingested:
        lines.append(f"  ingested {report.ingested} from the inbox")
    if report.halted:
        lines.append(f"  HALTED: {report.halt_reason}")
        if report.demoted_to:
            lines.append(f"  autonomy demoted to {report.demoted_to}")
    for a in report.applied:
        lines.append(f"  applied  {a.kind:<8} {a.target}  ({a.event_id})  inverse {a.inverse}")
    for d in report.decisions:
        if d["action"] != "apply":
            lines.append(f"  proposed {d['kind']:<8} {d['why']}")
    if report.graduation_suggested:
        lines.append(
            f"  graduation: {report.graduation_suggested} suggested - a node cannot promote "
            "itself; set it in kourob.yaml if you agree"
        )
    lines.append(f"  spent {report.spent:.4f} of {report.budget:.4f}")
    return "\n".join(lines)


__all__ = [
    "LEVELS",
    "REQUIRED_LEVEL",
    "Applied",
    "Decision",
    "TendError",
    "TendReport",
    "apply_change",
    "changes",
    "decide",
    "past_reports",
    "record_change",
    "render",
    "rollback",
    "tend",
]
