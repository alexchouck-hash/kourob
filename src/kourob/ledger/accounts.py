"""Balances, free allowances, and the accounts table.

Brief reference: section 4.4. KNP-3 section 4.

Credits are an internal ledger in v1. **No money moves.** Every entry is appended, never
edited; a balance is the sum of a caller's entries, computed on read. Settlement is
post-paid against a quote: the node answers, appends the receipt, and debits a price bounded
by the ceiling it quoted.
"""

from __future__ import annotations

from typing import Any

from kourob import events as ev
from kourob.store import Store

__milestone__ = "M4"

DEBIT = "debit"
CREDIT = "credit"
GRANT = "grant"


class Accounts:
    """One append-only table of movements, keyed by counterparty."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def _rows(self, caller: str | None = None) -> list[dict[str, Any]]:
        if self.store.stats("accounts")["rows"] == 0:
            return []
        if caller is None:
            return self.store.scan("accounts", order_by="id")
        return self.store.query(
            "SELECT * FROM accounts WHERE caller = $caller ORDER BY id", {"caller": caller}
        ).to_pylist()

    def balance(self, caller: str) -> float:
        return round(sum(float(r.get("delta") or 0.0) for r in self._rows(caller)), 9)

    def _move(
        self, caller: str, delta: float, kind: str, *, receipt_id: str | None, note: str
    ) -> dict:
        row = {
            "id": ev.new_id("acct_"),
            "caller": caller,
            "delta": delta,
            "kind": kind,
            "receipt_id": receipt_id,
            "note": note,
            "ts": ev.now().isoformat(),
        }
        self.store.append("accounts", [row])
        return row

    def debit(self, caller: str, amount: float, *, receipt_id: str, note: str = "") -> dict:
        """Charge a caller for a receipted answer. Balances may go negative: the free
        allowance is what stops a stranger running one up, and refusal is upstream of here."""
        if amount <= 0:
            return {}
        return self._move(caller, -amount, DEBIT, receipt_id=receipt_id, note=note)

    def credit(self, caller: str, amount: float, *, note: str = "") -> dict:
        return self._move(caller, amount, CREDIT, receipt_id=None, note=note)

    def grant(self, caller: str, amount: float, *, note: str = "bootstrap grant") -> dict:
        """The operator's stake in a node with no revenue yet (KNP-7 section 3.2)."""
        return self._move(caller, amount, GRANT, receipt_id=None, note=note)

    def statement(self) -> dict[str, float]:
        """Every counterparty's balance."""
        totals: dict[str, float] = {}
        for row in self._rows():
            totals[row["caller"]] = totals.get(row["caller"], 0.0) + float(row.get("delta") or 0.0)
        return {k: round(v, 9) for k, v in totals.items()}


__all__ = ["CREDIT", "DEBIT", "GRANT", "Accounts"]
