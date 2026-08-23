from __future__ import annotations

from collections.abc import Iterable

from src.models.transactions import MatchPair, Transaction


class ExactMatcher:
    def match(self, razorpay: Iterable[Transaction], bank: Iterable[Transaction], ledger: Iterable[Transaction]) -> tuple[list[MatchPair], set[str], set[str], set[str]]:
        bank_idx: dict[tuple[float, str, str], Transaction] = {}
        ledger_idx: dict[tuple[float, str, str], Transaction] = {}

        for b in bank:
            key = (round(b.amount, 2), b.txn_date.isoformat(), (b.reference or "").strip().lower())
            if key not in bank_idx:
                bank_idx[key] = b
        for l in ledger:
            key = (round(l.amount, 2), l.txn_date.isoformat(), (l.reference or "").strip().lower())
            if key not in ledger_idx:
                ledger_idx[key] = l

        matches: list[MatchPair] = []
        used_bank: set[str] = set()
        used_ledger: set[str] = set()
        used_razorpay: set[str] = set()

        for r in razorpay:
            key = (round(r.amount, 2), r.txn_date.isoformat(), (r.reference or "").strip().lower())
            b = bank_idx.get(key)
            l = ledger_idx.get(key)
            if b and l and b.txn_id not in used_bank and l.txn_id not in used_ledger:
                matches.append(
                    MatchPair(
                        razorpay_txn_id=r.txn_id,
                        bank_txn_id=b.txn_id,
                        ledger_txn_id=l.txn_id,
                        confidence=1.0,
                        method="exact",
                        notes="Exact amount + date + reference match",
                    )
                )
                used_razorpay.add(r.txn_id)
                used_bank.add(b.txn_id)
                used_ledger.add(l.txn_id)

        return matches, used_razorpay, used_bank, used_ledger
