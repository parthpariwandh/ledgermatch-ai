from __future__ import annotations

import pandas as pd

from src.matcher.pipeline import HybridReconciler
from src.models.transactions import ReconciliationBatch, Transaction


class LedgerMatchAgent:
    def __init__(self) -> None:
        self.reconciler = HybridReconciler()

    @staticmethod
    def _from_df(df: pd.DataFrame, source: str) -> list[Transaction]:
        return [
            Transaction(
                source=source,  # type: ignore[arg-type]
                txn_id=str(row["txn_id"]),
                amount=float(row["amount"]),
                txn_date=pd.to_datetime(row["txn_date"]).date(),
                reference=(str(row["reference"]) if pd.notna(row["reference"]) and str(row["reference"]).strip() else None),
                counterparty=str(row["counterparty"]),
                currency=str(row.get("currency", "INR") or "INR"),
            )
            for _, row in df.iterrows()
        ]

    def reconcile_from_dataframes(self, razorpay_df: pd.DataFrame, bank_df: pd.DataFrame, ledger_df: pd.DataFrame):
        batch = ReconciliationBatch(
            razorpay=self._from_df(razorpay_df, "razorpay"),
            bank=self._from_df(bank_df, "bank"),
            ledger=self._from_df(ledger_df, "ledger"),
        )
        return self.reconciler.reconcile(batch)

    def reconcile_from_csvs(self, razorpay_csv: str, bank_csv: str, ledger_csv: str):
        return self.reconcile_from_dataframes(
            pd.read_csv(razorpay_csv),
            pd.read_csv(bank_csv),
            pd.read_csv(ledger_csv),
        )
