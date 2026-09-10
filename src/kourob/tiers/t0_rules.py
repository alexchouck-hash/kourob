"""T0: deterministic rules and SQL views over silver, plus the exact-match cache.

Brief reference: sections 3.1 and 5.3. Promotion by exact replay: ADR-0008.

A rule is a regex over the question and a SQL query over silver. That shape is not a
simplification: it is exactly what KNP-5 section 3.3 mines from a cluster whose answers have
always been a function of its inputs, so a hand-written rule and a promoted one are the same
artefact and run down the same path.

T0 answers are `derived` (KNP-0 section 2): anyone holding the events can re-run them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kourob.store import Store
from kourob.tiers.base import Request, TierHandler, TierResult
from kourob.types import Tier

__milestone__ = "M1"

RULES_DIR = "tiers/t0/rules"


@dataclass
class Rule:
    """One mined or hand-written function from question shape to rows."""

    id: str
    pattern: re.Pattern[str]
    sql: str
    render: str = ""
    description: str = ""
    confidence: float = 1.0
    usage_count: int = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Rule:
        return cls(
            id=raw["id"],
            pattern=re.compile(raw["match"], re.IGNORECASE),
            sql=raw["sql"],
            render=raw.get("render", ""),
            description=raw.get("description", ""),
            confidence=float(raw.get("confidence", 1.0)),
            usage_count=int(raw.get("usage_count", 0)),
        )

    def bind(self, question: str) -> dict[str, str] | None:
        match = self.pattern.search(question)
        return match.groupdict() if match else None


def load_rules(node_dir: Path | str) -> list[Rule]:
    rules_dir = Path(node_dir) / RULES_DIR
    if not rules_dir.exists():
        return []
    return [
        Rule.from_dict(yaml.safe_load(p.read_text(encoding="utf-8")))
        for p in sorted(rules_dir.glob("*.yaml"))
    ]


class T0Rules(TierHandler):
    """The cheapest tier. A lookup, a rule, or nothing."""

    tier = Tier.T0

    def __init__(self, node_dir: Path | str, store: Store, *, base_cost: float = 0.0001) -> None:
        self.node_dir = Path(node_dir)
        self.store = store
        self.base_cost = base_cost
        self.rules = load_rules(node_dir)

    def available(self) -> bool:
        return bool(self.rules)

    def attempt(self, request: Request) -> TierResult:
        for rule in self.rules:
            params = rule.bind(request.question)
            if params is None:
                continue
            rows = self.store.query(rule.sql, params).to_pylist()
            if not rows:
                # The rule matched the question but the events do not support an answer.
                # That is a miss, not an empty answer: silence is not a fact.
                continue
            rule.usage_count += 1
            return TierResult(
                tier=Tier.T0,
                answered=True,
                confidence=rule.confidence,
                data=rows if len(rows) > 1 else rows[0],
                rendered=self._render(rule, rows),
                citations=[r["id"] for r in rows if r.get("id")],
                model_version=f"rule:{rule.id}",
                cost_credits=self.base_cost,
                detail=rule.description,
            )
        return TierResult.miss(Tier.T0, "no rule matched")

    @staticmethod
    def _render(rule: Rule, rows: list[dict[str, Any]]) -> str:
        if not rule.render:
            return "\n".join(f"- `{r.get('id')}`: {r}" for r in rows)
        lines = []
        for row in rows:
            try:
                lines.append(rule.render.format(**row))
            except (KeyError, IndexError):
                lines.append(str(row))
        return "\n".join(
            f"{line} [{row.get('id')}]" for line, row in zip(lines, rows, strict=False)
        )


__all__ = ["RULES_DIR", "Rule", "T0Rules", "load_rules"]
