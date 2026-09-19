"""Runner adapters. The ONLY place a vendor SDK may be imported. CI enforces this.

Brief reference: section 9 (Runner).

Adapters are registered lazily by name so importing `kourob` never imports a vendor SDK, and
a missing optional dependency is a missing *adapter*, not a broken package.
"""

from __future__ import annotations

from typing import Any

from kourob.runner.adapters.base import (
    Adapter,
    AdapterError,
    CallResult,
    Message,
    estimate_tokens,
)
from kourob.runner.adapters.local import LocalAdapter, ScriptedReply

__milestone__ = "M1"

#: Adapter name to the module that provides it. Vendor modules are imported on demand.
KNOWN = {
    "local": "kourob.runner.adapters.local",
    "claude_code": "kourob.runner.adapters.claude_code",
    "codex": "kourob.runner.adapters.codex",
    "openai": "kourob.runner.adapters.openai",
    "anthropic": "kourob.runner.adapters.anthropic",
    "gemini": "kourob.runner.adapters.gemini",
}


def build(name: str, **kw: Any) -> Adapter:
    """Construct an adapter by name. Raises AdapterError for one that is not built yet."""
    if name == "local":
        return LocalAdapter(**kw)
    if name not in KNOWN:
        raise AdapterError(f"no adapter {name!r}; known: {', '.join(sorted(KNOWN))}")
    raise AdapterError(
        f"adapter {name!r} is declared but not implemented yet (M2). "
        "Use the local adapter, or implement it in kourob/runner/adapters/."
    )


__all__ = [
    "KNOWN",
    "Adapter",
    "AdapterError",
    "CallResult",
    "LocalAdapter",
    "Message",
    "ScriptedReply",
    "build",
    "estimate_tokens",
]
