import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Quant Gap Terminal", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1rem;}
.small {font-family: monospace;}
</style>
""", unsafe_allow_html=True)

st.title("QUANT GAP BREAKOUT // PAPER TERMINAL")
st.caption("Rules-driven S&P 500 scanner • execution guardrails • audit feed")

db_path = "data/trading.db"
if Path(db_path).exists():
    db = sqlite3.connect(db_path)
    trades = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC", db)
    events = pd.read_sql_query("SELECT * FROM events ORDER BY id DESC LIMIT 200", db)
    db.close()
else:
    trades = pd.DataFrame()
    events = pd.DataFrame()

c1,c2,c3,c4 = st.columns(4)
c1.metric("TRADES", len(trades))
c2.metric("WIN RATE", f"{trades.pnl.gt(0).mean()*100:.1f}%" if len(trades) else "0.0%")
c3.metric("P&L", f"${trades.pnl.sum():,.2f}" if len(trades) else "$0.00")
c4.metric("OPEN", int((trades.status == "OPEN").sum()) if len(trades) else 0)

st.subheader("Cumulative P&L")
if len(trades):
    st.line_chart(trades.assign(cumulative_pnl=trades.pnl.cumsum()).set_index("id")["cumulative_pnl"])
else:
    st.info("No completed trades yet.")

st.subheader("Trade History")
st.dataframe(trades, use_container_width=True)

st.subheader("Decision / Event Feed")
st.dataframe(events, use_container_width=True)
