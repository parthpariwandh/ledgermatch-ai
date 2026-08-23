from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

COUNTERPARTIES = [
    "Acme Retail",
    "Nova Logistics",
    "Bluekart",
    "FreshFarm",
    "Urban Electronics",
    "GreenFuel",
    "CloudStay",
    "Metro Medics",
    "QuickFoods",
    "EduSpark",
]


def _make_base_records(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    start = date(2026, 4, 1)
    records: list[dict] = []
    for i in range(n):
        amount = round(rng.uniform(200.0, 15000.0), 2)
        d = start + timedelta(days=rng.randint(0, 90))
        ref = f"INV-{rng.randint(10000, 99999)}"
        records.append(
            {
                "base_id": f"TXN-{i+1:04d}",
                "amount": amount,
                "txn_date": d.isoformat(),
                "reference": ref,
                "counterparty": rng.choice(COUNTERPARTIES),
                "currency": "INR",
            }
        )
    return records


def build_dataset(n: int = 120, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = random.Random(seed)
    base = _make_base_records(n, seed)

    razorpay_rows, bank_rows, ledger_rows = [], [], []

    for row in base:
        rp = row.copy()
        rp["txn_id"] = f"RP-{row['base_id']}"
        razorpay_rows.append(rp)

        b = row.copy()
        b["txn_id"] = f"BK-{row['base_id']}"
        l = row.copy()
        l["txn_id"] = f"LD-{row['base_id']}"

        # Controlled noise patterns
        p = rng.random()
        if p < 0.15:  # fee leakage
            fee = round(rng.uniform(1.0, 25.0), 2)
            b["amount"] = round(max(1.0, b["amount"] - fee), 2)
        elif p < 0.30:  # date drift
            drift = rng.choice([-2, -1, 1, 2])
            new_date = pd.to_datetime(b["txn_date"]).date() + timedelta(days=drift)
            b["txn_date"] = new_date.isoformat()
        elif p < 0.42:  # missing reference
            l["reference"] = ""
        elif p < 0.50:  # hard negative in ledger
            l["amount"] = round(l["amount"] + rng.uniform(60.0, 400.0), 2)

        # textual noise
        if rng.random() < 0.25:
            b["counterparty"] = b["counterparty"].replace(" ", "")
        if rng.random() < 0.20 and l.get("reference"):
            l["reference"] = l["reference"].replace("INV", "INVOICE")

        bank_rows.append(b)
        ledger_rows.append(l)

    # extra unmatched rows
    for j in range(max(5, n // 20)):
        bank_rows.append(
            {
                "txn_id": f"BK-ORPHAN-{j+1:03d}",
                "amount": round(rng.uniform(500.0, 9000.0), 2),
                "txn_date": (date(2026, 7, 1) + timedelta(days=j)).isoformat(),
                "reference": f"MISC-{rng.randint(1000, 9999)}",
                "counterparty": rng.choice(COUNTERPARTIES),
                "currency": "INR",
            }
        )

    return pd.DataFrame(razorpay_rows), pd.DataFrame(bank_rows), pd.DataFrame(ledger_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic reconciliation datasets")
    parser.add_argument("--records", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rp, bk, ld = build_dataset(n=args.records, seed=args.seed)
    rp.to_csv(args.out / "razorpay.csv", index=False)
    bk.to_csv(args.out / "bank.csv", index=False)
    ld.to_csv(args.out / "ledger.csv", index=False)
    print(f"Generated datasets at {args.out.resolve()} with {len(rp)} razorpay rows")


if __name__ == "__main__":
    main()
