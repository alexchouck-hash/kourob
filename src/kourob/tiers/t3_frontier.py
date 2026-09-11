"""T3: a frontier model, called through runner/ so every token is logged and costed.

Brief reference: section 3.1 step 4. Grounding: KNP-0 I2 and KNP-2 section 5.

The expensive tier, and the one that can lie. So it does three things the cheaper tiers do
not have to:

1. **Retrieves before it answers.** The model sees the node's own events, labelled with
   their ids, and is told to answer only from them.
2. **Validates every citation it returns.** A cited id that is not in silver is a
   fabrication, and it is dropped rather than passed on.
3. **Declines rather than guessing.** An answer with no surviving citation is a miss, not
   an answer, because emitting one would launder a guess into the provenance graph — the
   worst failure KNP-2 section 5 names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from kourob.manifest import Manifest
from kourob.runner.adapters import AdapterError, Message
from kourob.runner.run import Runner
from kourob.store import Store
from kourob.tiers.base import Request, TierHandler, TierResult
from kourob.types import Tier

__milestone__ = "M1"

MAX_CONTEXT_EVENTS = 12
_WORD = re.compile(r"[a-z0-9][a-z0-9-]{2,}")

SYSTEM = """You answer only from the events given to you.

Rules, in order of importance:
1. Every claim you make must be supported by one of the numbered events below. If the
   events do not support an answer, say so and cite nothing.
2. Cite by event id, exactly as given. Never invent an id.
3. Prefer a short answer that is fully supported over a complete one that is not.

Reply with JSON only, no prose around it:
{"answer": "<your answer>", "citations": ["evt_..."], "confidence": 0.0}

confidence is your own estimate that the answer is both correct and supported by the cited
events. Be honest; a low number costs nothing and a wrong high one costs the caller."""


class T3Frontier(TierHandler):
    """Retrieve, ask, verify the citations, or decline."""

    tier = Tier.T3

    def __init__(
        self,
        node_dir: Path | str,
        store: Store,
        runner: Runner,
        manifest: Manifest,
        *,
        adapter: str = "local",
    ) -> None:
        self.node_dir = Path(node_dir)
        self.store = store
        self.runner = runner
        self.manifest = manifest
        self.adapter = adapter

    def available(self) -> bool:
        try:
            return self.runner.adapter(self.adapter).available()
        except AdapterError:
            return False

    # -------------------------------------------------------------------------- retrieve

    def retrieve(self, question: str, limit: int = MAX_CONTEXT_EVENTS) -> list[dict[str, Any]]:
        """Candidate events, by word overlap with the question.

        Keyword overlap, not embeddings. v1 has no vector store on purpose (brief section
        10), and for a node whose scope is narrow by construction, overlap over a few
        thousand typed events is both adequate and explainable.
        """
        if self.store.stats("silver")["rows"] == 0:
            return []
        words = set(_WORD.findall(question.lower()))
        if not words:
            return []
        rows = self.store.scan("silver")
        scored = []
        for row in rows:
            text = json.dumps(row.get("payload") or {}).lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda pair: -pair[0])
        return [row for _, row in scored[:limit]]

    # ---------------------------------------------------------------------------- answer

    def attempt(self, request: Request) -> TierResult:
        events = self.retrieve(request.question)
        if not events:
            return TierResult.miss(Tier.T3, "no events matched the question")

        try:
            call = self.runner.call(
                [
                    Message("system", SYSTEM),
                    Message("user", self._prompt(request.question, events)),
                ],
                tier=Tier.T3,
                purpose="answer",
                adapter=self.adapter,
            )
        except AdapterError as exc:
            return TierResult.miss(Tier.T3, f"adapter unavailable: {exc}")

        cost = self.runner.price(call)
        parsed = _parse(call.text)
        if parsed is None:
            return TierResult(
                tier=Tier.T3,
                answered=False,
                cost_credits=cost,
                detail="model did not return the requested JSON",
            )

        known = {row["id"] for row in events}
        cited = [c for c in parsed["citations"] if c in known]
        fabricated = [c for c in parsed["citations"] if c not in known]

        if not cited:
            return TierResult(
                tier=Tier.T3,
                answered=False,
                cost_credits=cost,
                detail=(
                    f"answer cited nothing in this node's events "
                    f"({len(fabricated)} fabricated id(s))"
                    if fabricated
                    else "answer cited nothing"
                ),
            )

        # Fabricated citations are evidence about the model, not about the world. They cost
        # confidence rather than invalidating an otherwise-grounded answer.
        confidence = parsed["confidence"] * (1.0 if not fabricated else 0.5)
        return TierResult(
            tier=Tier.T3,
            answered=True,
            confidence=confidence,
            data={"answer": parsed["answer"], "events": [r["id"] for r in events]},
            rendered=parsed["answer"] + "".join(f" [{c}]" for c in cited),
            citations=cited,
            model_version=f"frontier:{call.adapter}:{call.model}",
            cost_credits=cost,
            detail=f"{len(fabricated)} fabricated citation(s) dropped" if fabricated else "",
        )

    @staticmethod
    def _prompt(question: str, events: list[dict[str, Any]]) -> str:
        lines = ["Events:"]
        for row in events:
            payload = json.dumps(row.get("payload") or {}, sort_keys=True)
            lines.append(f"  {row['id']}  ({row.get('schema_ref')})  {payload}")
        lines.append("")
        lines.append(f"Question: {question}")
        return "\n".join(lines)


def _parse(text: str) -> dict[str, Any] | None:
    """Pull the JSON object out of a model reply, tolerating fences and stray prose."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-z]*\n|\n```$", "", candidate).strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or "answer" not in parsed:
        return None
    citations = parsed.get("citations") or []
    return {
        "answer": str(parsed["answer"]).strip(),
        "citations": [str(c) for c in citations if isinstance(c, str)],
        "confidence": _clamp(parsed.get("confidence", 0.5)),
    }


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


__all__ = ["MAX_CONTEXT_EVENTS", "SYSTEM", "T3Frontier"]
