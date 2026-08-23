from __future__ import annotations

import pandas as pd
import streamlit as st

from src.agent.reconciliation_agent import LedgerMatchAgent

st.set_page_config(page_title="LedgerMatch AI", layout="wide")
st.title("LedgerMatch AI - Multi-Source Reconciliation")
st.caption("Razorpay AI Buildathon 2026 | Track 4: AI Finance Controller")

agent = LedgerMatchAgent()

st.sidebar.header("Input Data")
use_sample = st.sidebar.checkbox("Use sample data from /data", value=True)

if use_sample:
    razorpay_df = pd.read_csv("data/razorpay.csv")
    bank_df = pd.read_csv("data/bank.csv")
    ledger_df = pd.read_csv("data/ledger.csv")
else:
    razorpay_file = st.sidebar.file_uploader("Razorpay settlements CSV", type="csv")
    bank_file = st.sidebar.file_uploader("Bank statement CSV", type="csv")
    ledger_file = st.sidebar.file_uploader("Internal ledger CSV", type="csv")
    if not (razorpay_file and bank_file and ledger_file):
        st.info("Upload all three CSV files to run reconciliation.")
        st.stop()
    razorpay_df = pd.read_csv(razorpay_file)
    bank_df = pd.read_csv(bank_file)
    ledger_df = pd.read_csv(ledger_file)

if st.button("Run Reconciliation", type="primary"):
    report = agent.reconcile_from_dataframes(razorpay_df, bank_df, ledger_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", report.total_ground_truth_records)
    c2.metric("Matched", report.matched_count)
    c3.metric("Match Rate", f"{report.exact_match_rate:.2%}")

    st.subheader("Matched Pairs")
    st.dataframe(pd.DataFrame([m.model_dump() for m in report.matched_pairs]), use_container_width=True, height=350)

    st.subheader("Prioritized Exceptions")
    st.dataframe(pd.DataFrame([e.model_dump() for e in report.exceptions]), use_container_width=True, height=350)
