"""The Adapter interface: complete(messages) returns a CallResult with token counts.

Brief reference: section 9 (Runner).

An adapter is the *only* place a vendor SDK may be imported (AGENTS.md section 4, enforced
by `tests/test_rails.py`). It does one thing: turn messages into text, and report honestly
what that consumed. It does not price, log, retry, or decide — the runner does those, once,
for every vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

__milestone__ = "M1"

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass
class CallResult:
    """What one model call produced and what it consumed.

    Token counts are **measured**, never estimated (KNP-3 section 1). An adapter that
    cannot report real counts must say so with `tokens_estimated=True` rather than guess
    silently, because the whole cost curve is denominated in these numbers.
    """

    text: str
    model: str
    adapter: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    tokens_estimated: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class AdapterError(RuntimeError):
    """A call that could not be made. Distinct from a call that returned something bad."""


class Adapter(ABC):
    """One vendor, one transport."""

    name: str = "adapter"

    @abstractmethod
    def complete(self, messages: list[Message], **opts: Any) -> CallResult:
        """Run one completion. Raise AdapterError if the call cannot be made at all."""

    def available(self) -> bool:
        """Whether this adapter can run right now: binary present, key set, host reachable."""
        return True


def estimate_tokens(text: str) -> int:
    """A rough token count for adapters that do not report one.

    Deliberately crude and deliberately labelled: any CallResult built on this sets
    `tokens_estimated`, so a cost curve computed from estimates can be told apart from one
    computed from measurements. Four characters per token is close enough to notice a
    tenfold error and not close enough to trust to two decimal places.
    """
    return max(1, len(text) // 4)


__all__ = ["Adapter", "AdapterError", "CallResult", "Message", "Role", "estimate_tokens"]
