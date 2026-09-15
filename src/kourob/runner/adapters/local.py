"""Local adapter: ollama or vLLM over HTTP, and the scripted mock every test uses.

Brief reference: section 9 (Runner). DEFAULTS.md: model calls in tests are mocked through
the runner's `local` adapter.

The two modes share a class on purpose. A test that scripts responses exercises the same
logging, pricing and validation path as a real call, so the thing tests prove is the thing
production runs. A separate mock object would let those two drift, and the drift would be
invisible until a cost number was wrong.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kourob.runner.adapters.base import (
    Adapter,
    AdapterError,
    CallResult,
    Message,
    estimate_tokens,
)

__milestone__ = "M1"

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:3b"


@dataclass
class ScriptedReply:
    """One canned response, chosen by a regex over the rendered prompt."""

    when: str
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"

    def matches(self, prompt: str) -> bool:
        return re.search(self.when, prompt, re.IGNORECASE | re.DOTALL) is not None


@dataclass
class LocalAdapter(Adapter):
    """A local model, or a script standing in for one."""

    name: str = "local"
    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    timeout_s: float = 60.0
    script: list[ScriptedReply] = field(default_factory=list)
    fallback: str | Callable[[str], str] | None = None
    calls: list[list[Message]] = field(default_factory=list)

    #: Set by `scripted()`. A scripted adapter never touches the network, which is what
    #: makes "no network in unit tests" checkable rather than a promise.
    offline: bool = False

    @classmethod
    def scripted(cls, replies: list[ScriptedReply] | None = None, **kw: Any) -> LocalAdapter:
        return cls(script=list(replies or []), offline=True, model="scripted", **kw)

    def available(self) -> bool:
        if self.offline:
            return True
        try:
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=2.0):
                return True
        except (urllib.error.URLError, OSError, TimeoutError):
            return False

    def complete(self, messages: list[Message], **opts: Any) -> CallResult:
        self.calls.append(list(messages))
        prompt = render(messages)
        started = time.perf_counter()

        result = self._scripted(prompt) if self.offline else self._http(messages, prompt, **opts)

        result.latency_ms = (time.perf_counter() - started) * 1000
        return result

    # ------------------------------------------------------------------------- scripted

    def _scripted(self, prompt: str) -> CallResult:
        for reply in self.script:
            if reply.matches(prompt):
                return CallResult(
                    text=reply.text,
                    model=self.model,
                    adapter=self.name,
                    prompt_tokens=reply.prompt_tokens or estimate_tokens(prompt),
                    completion_tokens=reply.completion_tokens or estimate_tokens(reply.text),
                    finish_reason=reply.finish_reason,
                    tokens_estimated=not (reply.prompt_tokens and reply.completion_tokens),
                )
        if self.fallback is None:
            raise AdapterError(
                "scripted adapter has no reply for this prompt and no fallback. "
                "An unscripted call in a test is a test asking a question it did not mean "
                f"to ask. Prompt began: {prompt[:120]!r}"
            )
        text = self.fallback(prompt) if callable(self.fallback) else self.fallback
        return CallResult(
            text=text,
            model=self.model,
            adapter=self.name,
            prompt_tokens=estimate_tokens(prompt),
            completion_tokens=estimate_tokens(text),
            tokens_estimated=True,
        )

    # ----------------------------------------------------------------------------- http

    def _http(self, messages: list[Message], prompt: str, **opts: Any) -> CallResult:
        payload = {
            "model": opts.get("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": opts.get("temperature", 0.0)},
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"local model at {self.host} did not answer: {exc}") from exc

        text = (body.get("message") or {}).get("content", "")
        prompt_tokens = int(body.get("prompt_eval_count") or 0)
        completion_tokens = int(body.get("eval_count") or 0)
        return CallResult(
            text=text,
            model=str(body.get("model", self.model)),
            adapter=self.name,
            prompt_tokens=prompt_tokens or estimate_tokens(prompt),
            completion_tokens=completion_tokens or estimate_tokens(text),
            finish_reason=str(body.get("done_reason", "stop")),
            tokens_estimated=not (prompt_tokens and completion_tokens),
            raw=body,
        )


def render(messages: list[Message]) -> str:
    """The prompt as one string, for matching and for token estimation."""
    return "\n\n".join(f"[{m.role}] {m.content}" for m in messages)


__all__ = ["DEFAULT_HOST", "DEFAULT_MODEL", "LocalAdapter", "ScriptedReply", "render"]
