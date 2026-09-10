"""The ledger: signed, hash-chained receipts, plus accounts and pricing.

Brief reference: section 4, ADR-0003.

v1 is a per-node append-only receipt log, hash-chained and ed25519-signed. v1.1 publishes
a Merkle root per node to the set registry. Public anchoring is deferred until there are
three or more independent operators (brief section 4.2).
"""

from __future__ import annotations

from kourob.ledger.outcome import Outcome, OutcomeSource, Verdict
from kourob.ledger.receipt import SIGNED_FIELDS, Receipt

__milestone__ = "M1"
__all__ = ["SIGNED_FIELDS", "Outcome", "OutcomeSource", "Receipt", "Verdict"]
