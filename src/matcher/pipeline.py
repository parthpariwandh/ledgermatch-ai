from __future__ import annotations

from src.matcher.exact_matcher import ExactMatcher
from src.matcher.fuzzy_matcher import FuzzyMatcher
from src.matcher.llm_matcher import LLMMatcher
from src.models.transactions import ExceptionCase, ReconciliationBatch, ReconciliationReport


class HybridReconciler:
    def __init__(self) -> None:
        self.exact_matcher = ExactMatcher()
        self.fuzzy_matcher = FuzzyMatcher()
        self.llm_matcher = LLMMatcher()

    def reconcile(self, batch: ReconciliationBatch) -> ReconciliationReport:
        exact_matches, used_r, used_b, used_l = self.exact_matcher.match(batch.razorpay, batch.bank, batch.ledger)
        fuzzy_matches, used_r, used_b, used_l, ambiguous = self.fuzzy_matcher.match(batch.razorpay, batch.bank, batch.ledger, used_r, used_b, used_l)
        llm_matches, used_r, used_b, used_l = self.llm_matcher.match(ambiguous, used_r, used_b, used_l)

        matches = exact_matches + fuzzy_matches + llm_matches

        exceptions: list[ExceptionCase] = []
        unmatched_razorpay = [r for r in batch.razorpay if r.txn_id not in used_r]
        unmatched_bank = [b for b in batch.bank if b.txn_id not in used_b]
        unmatched_ledger = [l for l in batch.ledger if l.txn_id not in used_l]

        def _root_cause(r):
            ref = (r.reference or "").strip().lower()
            bank_ref_matches = [b for b in batch.bank if (b.reference or "").strip().lower() == ref] if ref else []
            ledger_ref_matches = [l for l in batch.ledger if (l.reference or "").strip().lower() == ref] if ref else []

            if not ref:
                return "Missing reference; likely manual tagging gap", "medium"
            if bank_ref_matches and any(abs(b.amount - r.amount) > 2.0 for b in bank_ref_matches):
                return "Probable fee leakage or settlement deductions (amount mismatch)", "high"
            if bank_ref_matches and any(abs((b.txn_date - r.txn_date).days) > 2 for b in bank_ref_matches):
                return "Settlement timing drift (date mismatch across systems)", "medium"
            if ledger_ref_matches and any((not l.reference) for l in ledger_ref_matches):
                return "Ledger metadata quality issue (missing/blank reference)", "medium"
            if ledger_ref_matches and any(abs(l.amount - r.amount) > 50.0 for l in ledger_ref_matches):
                return "Potential hard negative or ledger posting error", "high"
            return "Missing counterpart in bank and/or ledger", "high"

        for r in unmatched_razorpay:
            reason, priority = _root_cause(r)
            exceptions.append(
                ExceptionCase(
                    priority=priority,
                    reason=reason,
                    razorpay_txn_id=r.txn_id,
                    details=f"Amount={r.amount:.2f}, Date={r.txn_date.isoformat()}, Counterparty={r.counterparty}",
                )
            )

        for b in unmatched_bank[:20]:
            exceptions.append(
                ExceptionCase(
                    priority="low",
                    reason="Bank-only transaction (possible settlement timing drift)",
                    bank_txn_id=b.txn_id,
                    details=f"Amount={b.amount:.2f}, Date={b.txn_date.isoformat()}",
                )
            )
        for l in unmatched_ledger[:20]:
            exceptions.append(
                ExceptionCase(
                    priority="low",
                    reason="Ledger-only transaction (possible posting delay or internal error)",
                    ledger_txn_id=l.txn_id,
                    details=f"Amount={l.amount:.2f}, Date={l.txn_date.isoformat()}",
                )
            )

        priority_order = {"high": 0, "medium": 1, "low": 2}
        exceptions.sort(key=lambda e: (priority_order[e.priority], e.reason))

        total = len(batch.razorpay)
        matched_count = len(matches)
        exact_count = len(exact_matches)
        return ReconciliationReport(
            total_ground_truth_records=total,
            matched_count=matched_count,
            exact_match_rate=(exact_count / total) if total else 0.0,
            matched_pairs=matches,
            exceptions=exceptions,
        )
