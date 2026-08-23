from __future__ import annotations

import argparse
from pathlib import Path

from src.agent.reconciliation_agent import LedgerMatchAgent


def format_report(report) -> str:
    lines = []
    lines.append("=== LedgerMatch AI Evaluation ===")
    lines.append(f"Total Razorpay Records: {report.total_ground_truth_records}")
    lines.append(f"Matched Records: {report.matched_count}")
    lines.append(f"Exact Match Rate: {report.exact_match_rate:.2%}")
    method_counts = {"exact": 0, "fuzzy": 0, "llm": 0}
    for m in report.matched_pairs:
        method_counts[m.method] += 1
    lines.append(f"Method Split: exact={method_counts['exact']}, fuzzy={method_counts['fuzzy']}, llm={method_counts['llm']}")
    lines.append("")
    lines.append("Matched Pairs (first 25):")
    for m in report.matched_pairs[:25]:
        lines.append(f"- {m.razorpay_txn_id} <-> {m.bank_txn_id} <-> {m.ledger_txn_id} [{m.method}, {m.confidence:.2f}]")
    lines.append("")
    lines.append("Prioritized Exceptions (first 25):")
    for ex in report.exceptions[:25]:
        lines.append(
            f"- [{ex.priority.upper()}] {ex.reason} | rp={ex.razorpay_txn_id} bank={ex.bank_txn_id} ledger={ex.ledger_txn_id}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full-batch reconciliation evaluation")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Directory containing razorpay.csv, bank.csv, ledger.csv")
    args = parser.parse_args()

    agent = LedgerMatchAgent()
    report = agent.reconcile_from_csvs(
        str(args.data_dir / "razorpay.csv"),
        str(args.data_dir / "bank.csv"),
        str(args.data_dir / "ledger.csv"),
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
