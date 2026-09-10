"""Every model call goes through here, so it is logged to logs/calls.parquet.

Brief reference: sections 9, 13.5.
Status: stub. Implemented in M1.
"""

from __future__ import annotations

from kourob.runner.adapters import Adapter, AdapterError, CallResult, LocalAdapter, Message
from kourob.runner.run import CallRecord, Runner

__milestone__ = "M1"
__all__ = [
    "Adapter",
    "AdapterError",
    "CallRecord",
    "CallResult",
    "LocalAdapter",
    "Message",
    "Runner",
]
