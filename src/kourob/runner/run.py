"""The vendor-neutral runner and its call log.

Brief reference: section 9 (Runner). AGENTS.md section 4.

Every model call in the package goes through here. Not as a style preference: an unlogged
call is an unmetered cost, and a node that cannot see what it spent cannot compute the one
number the evolve loop optimises (KNP-5 section 1). `tests/test_rails.py` enforces that no
vendor SDK is imported outside `runner/adapters/`.

The runner prices, logs and times. It does not retry, cache or fall back — those are
cascade decisions and they belong where the confidence bars are.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kourob import events as ev
from kourob.manifest import Manifest
from kourob.runner.adapters import Adapter, AdapterError, CallResult, Message, build
from kourob.store import Store
from kourob.types import Tier

__milestone__ = "M1"


@dataclass
class CallRecord:
    """One row of `logs/calls.parquet`. The evolve loop reads these."""

    id: str
    ts: str
    tier: str
    purpose: str
    adapter: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    tokens_estimated: bool
    cost_credits: float
    latency_ms: float
    finish_reason: str
    ok: bool
    error: str | None = None

    def as_row(self) -> dict[str, Any]:
        return self.__dict__.copy()


class Runner:
    """One entry point for every model call a node makes."""

    def __init__(
        self,
        manifest: Manifest,
        *,
        store: Store | None = None,
        adapters: dict[str, Adapter] | None = None,
    ) -> None:
        self.manifest = manifest
        self.store = store
        self._adapters: dict[str, Adapter] = dict(adapters or {})

    def adapter(self, name: str) -> Adapter:
        if name not in self._adapters:
            self._adapters[name] = build(name)
        return self._adapters[name]

    def price(self, result: CallResult) -> float:
        """Credits for one call, from the counts the adapter reported."""
        rate = self.manifest.pricing.token_rate(result.model, result.adapter)
        return (
            result.prompt_tokens * rate.prompt + result.completion_tokens * rate.completion
        ) / 1000.0

    def call(
        self,
        messages: list[Message],
        *,
        tier: Tier,
        purpose: str,
        adapter: str = "local",
        **opts: Any,
    ) -> CallResult:
        """Make one call, price it, log it. Raises AdapterError; logs the failure first.

        A failed call still costs latency and sometimes tokens, and it is evidence about a
        route or a model. Logging it before re-raising is the difference between a node
        that knows its own reliability and one that only remembers its successes.
        """
        try:
            result = self.adapter(adapter).complete(messages, **opts)
        except AdapterError as exc:
            self._log(
                tier=tier,
                purpose=purpose,
                adapter=adapter,
                result=None,
                cost=0.0,
                error=str(exc),
            )
            raise

        cost = self.price(result)
        self._log(tier=tier, purpose=purpose, adapter=adapter, result=result, cost=cost)
        return result

    def _log(
        self,
        *,
        tier: Tier,
        purpose: str,
        adapter: str,
        result: CallResult | None,
        cost: float,
        error: str | None = None,
    ) -> None:
        if self.store is None:
            return
        record = CallRecord(
            id=ev.new_id("call_"),
            ts=ev.now().isoformat(),
            tier=tier.value,
            purpose=purpose,
            adapter=adapter,
            model=result.model if result else "-",
            prompt_tokens=result.prompt_tokens if result else 0,
            completion_tokens=result.completion_tokens if result else 0,
            tokens_estimated=result.tokens_estimated if result else False,
            cost_credits=cost,
            latency_ms=result.latency_ms if result else 0.0,
            finish_reason=result.finish_reason if result else "error",
            ok=result is not None,
            error=error,
        )
        self.store.append("calls", [record.as_row()])

    def spend(self) -> float:
        """Everything this node has spent on model calls, from the log rather than memory."""
        if self.store is None or self.store.stats("calls")["rows"] == 0:
            return 0.0
        rows = self.store.query("SELECT sum(cost_credits) AS total FROM calls").to_pylist()
        return float(rows[0]["total"] or 0.0)


def for_node(node_dir: Path | str, manifest: Manifest, store: Store, **kw: Any) -> Runner:
    """Build the runner a node serves from."""
    return Runner(manifest, store=store, **kw)


__all__ = ["CallRecord", "Runner", "for_node"]
