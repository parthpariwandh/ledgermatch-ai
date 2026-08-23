from datetime import date

from src.matcher.pipeline import HybridReconciler
from src.models.transactions import ReconciliationBatch, Transaction


def _txn(source: str, txn_id: str, amount: float, day: int, reference: str, counterparty: str) -> Transaction:
    return Transaction(
        source=source,  # type: ignore[arg-type]
        txn_id=txn_id,
        amount=amount,
        txn_date=date(2026, 5, day),
        reference=reference,
        counterparty=counterparty,
        currency="INR",
    )


def test_pipeline_exact_and_fuzzy_match() -> None:
    batch = ReconciliationBatch(
        razorpay=[
            _txn("razorpay", "RP-1", 1000.0, 5, "INV-100", "Acme Retail"),
            _txn("razorpay", "RP-2", 2500.0, 7, "INV-200", "Nova Logistics"),
        ],
        bank=[
            _txn("bank", "BK-1", 1000.0, 5, "INV-100", "Acme Retail"),
            _txn("bank", "BK-2", 2499.5, 8, "INV 200", "NovaLogistics"),
        ],
        ledger=[
            _txn("ledger", "LD-1", 1000.0, 5, "INV-100", "Acme Retail"),
            _txn("ledger", "LD-2", 2500.4, 7, "INV-200", "Nova Logistics"),
        ],
    )

    report = HybridReconciler().reconcile(batch)

    assert report.matched_count == 2
    methods = {m.method for m in report.matched_pairs}
    assert "exact" in methods
    assert "fuzzy" in methods
