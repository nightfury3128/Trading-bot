import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


_dotenv_path = Path(__file__).resolve().parents[1] / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY (set environment variables or use local .env)")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


st.set_page_config(page_title="Trading Bot Dashboard", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
      .metric-card { padding: 14px 16px; border-radius: 16px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); }
      .muted { opacity: 0.75; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Trading Bot Dashboard")


@st.cache_data(ttl=20)
def load_performance():
    rows = (
        sb.table("performance")
        .select("date,total_value")
        .order("date", desc=False)
        .limit(5000)
        .execute()
        .data
        or []
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["total_value"] = pd.to_numeric(df["total_value"], errors="coerce")
    df = df.dropna(subset=["date", "total_value"]).sort_values("date")
    return df


@st.cache_data(ttl=20)
def load_account_cash():
    rows = sb.table("account").select("*").eq("id", 1).execute().data or []
    if not rows:
        return None
    return float(rows[0].get("cash") or 0.0)


@st.cache_data(ttl=20)
def load_portfolio():
    rows = sb.table("portfolio").select("*").execute().data or []
    return rows


perf = load_performance()
cash = load_account_cash()
portfolio = load_portfolio()

if perf.empty:
    st.info("No performance history yet. Run `main.py` at least once to populate the `performance` table.")
    st.stop()

latest_value = float(perf["total_value"].iloc[-1])
first_value = float(perf["total_value"].iloc[0])
prev_value = float(perf["total_value"].iloc[-2]) if len(perf) >= 2 else None

profit_since_start = latest_value - first_value
profit_day = (latest_value - prev_value) if prev_value is not None else None

invested = (latest_value - cash) if cash is not None else None

top = st.columns(5)
with top[0]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Total value", f"${latest_value:,.2f}", f"${profit_day:,.2f}" if profit_day is not None else None)
    st.markdown("</div>", unsafe_allow_html=True)
with top[1]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("P/L since start", f"${profit_since_start:,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)
with top[2]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Cash left", f"${cash:,.2f}" if cash is not None else "—")
    st.markdown("</div>", unsafe_allow_html=True)
with top[3]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Invested (open)", f"${invested:,.2f}" if invested is not None else "—")
    st.markdown("</div>", unsafe_allow_html=True)
with top[4]:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Open positions", f"{len(portfolio)}")
    st.markdown("</div>", unsafe_allow_html=True)

st.subheader("Performance")
st.line_chart(perf.set_index("date")["total_value"])

st.subheader("Current portfolio")
if portfolio:
    dfp = pd.DataFrame(portfolio)
    st.dataframe(dfp, use_container_width=True, hide_index=True)
else:
    st.write("No open positions.")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

