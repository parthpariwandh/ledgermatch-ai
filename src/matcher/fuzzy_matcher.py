from __future__ import annotations

from rapidfuzz import fuzz

from src.models.transactions import MatchPair, Transaction


class FuzzyMatcher:
    def __init__(self, reference_threshold: float = 80.0, counterparty_threshold: float = 75.0, amount_tolerance: float = 2.0, date_tolerance_days: int = 2) -> None:
        self.reference_threshold = reference_threshold
        self.counterparty_threshold = counterparty_threshold
        self.amount_tolerance = amount_tolerance
        self.date_tolerance_days = date_tolerance_days

    def _score(self, left: Transaction, right: Transaction) -> float:
        def _norm(text: str | None) -> str:
            if not text:
                return ""
            return "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace()).strip()

        ref_left = _norm(left.reference)
        ref_right = _norm(right.reference)
        cp_left = _norm(left.counterparty)
        cp_right = _norm(right.counterparty)

        ref_score = max(fuzz.token_sort_ratio(ref_left, ref_right), fuzz.ratio(ref_left, ref_right))
        cp_score = max(fuzz.token_sort_ratio(cp_left, cp_right), fuzz.ratio(cp_left, cp_right), fuzz.partial_ratio(cp_left, cp_right))
        date_delta = abs((left.txn_date - right.txn_date).days)
        amount_delta = abs(left.amount - right.amount)

        if date_delta > self.date_tolerance_days or amount_delta > self.amount_tolerance:
            return 0.0

        amount_score = max(0.0, 100.0 - (amount_delta * 20.0))
        date_score = max(0.0, 100.0 - (date_delta * 30.0))
        return (0.35 * ref_score) + (0.35 * cp_score) + (0.15 * amount_score) + (0.15 * date_score)

    def match(self, razorpay: list[Transaction], bank: list[Transaction], ledger: list[Transaction], used_r: set[str], used_b: set[str], used_l: set[str]) -> tuple[list[MatchPair], set[str], set[str], set[str], list[tuple[Transaction, list[Transaction], list[Transaction]]]]:
        matches: list[MatchPair] = []
        ambiguous: list[tuple[Transaction, list[Transaction], list[Transaction]]] = []

        for r in razorpay:
            if r.txn_id in used_r:
                continue

            bank_candidates = [b for b in bank if b.txn_id not in used_b and abs(b.amount - r.amount) <= self.amount_tolerance and abs((b.txn_date - r.txn_date).days) <= self.date_tolerance_days]
            ledger_candidates = [l for l in ledger if l.txn_id not in used_l and abs(l.amount - r.amount) <= self.amount_tolerance and abs((l.txn_date - r.txn_date).days) <= self.date_tolerance_days]

            if not bank_candidates or not ledger_candidates:
                continue

            best_pair: tuple[Transaction, Transaction] | None = None
            best_score = 0.0
            second_best = 0.0

            for b in bank_candidates:
                rb = self._score(r, b)
                if rb < self.reference_threshold:
                    continue
                for l in ledger_candidates:
                    rl = self._score(r, l)
                    if rl < self.reference_threshold:
                        continue
                    bl = self._score(b, l)
                    score = (rb + rl + bl) / 3.0
                    if score > best_score:
                        second_best = best_score
                        best_score = score
                        best_pair = (b, l)
                    elif score > second_best:
                        second_best = score

            if best_pair and best_score >= self.counterparty_threshold and (best_score - second_best) >= 8.0:
                b, l = best_pair
                matches.append(
                    MatchPair(
                        razorpay_txn_id=r.txn_id,
                        bank_txn_id=b.txn_id,
                        ledger_txn_id=l.txn_id,
                        confidence=min(best_score / 100.0, 0.95),
                        method="fuzzy",
                        notes=f"Fuzzy score={best_score:.1f}",
                    )
                )
                used_r.add(r.txn_id)
                used_b.add(b.txn_id)
                used_l.add(l.txn_id)
            elif bank_candidates and ledger_candidates:
                ambiguous.append((r, bank_candidates[:3], ledger_candidates[:3]))

        return matches, used_r, used_b, used_l, ambiguous
