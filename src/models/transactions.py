from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


SourceType = Literal["razorpay", "bank", "ledger"]


class Transaction(BaseModel):
    source: SourceType
    txn_id: str = Field(..., min_length=1)
    amount: float
    txn_date: date
    reference: str | None = None
    counterparty: str
    currency: str = "INR"


class MatchPair(BaseModel):
    razorpay_txn_id: str
    bank_txn_id: str
    ledger_txn_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: Literal["exact", "fuzzy", "llm"]
    notes: str | None = None


class ExceptionCase(BaseModel):
    priority: Literal["high", "medium", "low"]
    reason: str
    razorpay_txn_id: str | None = None
    bank_txn_id: str | None = None
    ledger_txn_id: str | None = None
    details: str | None = None


class ReconciliationBatch(BaseModel):
    razorpay: list[Transaction]
    bank: list[Transaction]
    ledger: list[Transaction]

    @model_validator(mode="after")
    def ensure_sources(self) -> "ReconciliationBatch":
        for source, txns in [
            ("razorpay", self.razorpay),
            ("bank", self.bank),
            ("ledger", self.ledger),
        ]:
            for txn in txns:
                if txn.source != source:
                    raise ValueError(f"Transaction {txn.txn_id} has wrong source {txn.source!r}, expected {source!r}")
        return self


class ReconciliationReport(BaseModel):
    total_ground_truth_records: int
    matched_count: int
    exact_match_rate: float
    matched_pairs: list[MatchPair]
    exceptions: list[ExceptionCase]
