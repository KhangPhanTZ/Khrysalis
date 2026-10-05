"""Streamlit dashboard: `uv run --extra apps streamlit run apps/dashboard/app.py`."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from moneyflow.config import get_settings
from moneyflow.data.cache import PriceCache

REPORT_DIR = Path("reports_out")

st.set_page_config(page_title="MoneyFlow Agents", layout="wide")
st.title("MoneyFlow Agents")
st.caption("Hệ thống chỉ hỗ trợ phân tích, không phải khuyến nghị đầu tư.")

cache = PriceCache(get_settings().moneyflow_db_path)
signals = cache.read_signals()

tab_rank, tab_report, tab_chart = st.tabs(["Xếp hạng", "Báo cáo", "Biểu đồ"])

with tab_rank:
    if signals.empty:
        st.info("Chưa có tín hiệu. Chạy `uv run moneyflow screen` trước.")
    else:
        dates = sorted(signals["run_date"].unique(), reverse=True)
        picked = st.selectbox("Ngày", dates)
        day = signals[signals["run_date"] == picked].sort_values("rank")
        st.dataframe(
            day[["rank", "ticker", "flow_score"]], hide_index=True, use_container_width=True
        )

with tab_report:
    files = sorted(REPORT_DIR.glob("*.md"), reverse=True)
    if not files:
        st.info("Chưa có báo cáo. Chạy `uv run moneyflow run`.")
    else:
        f = st.selectbox("Báo cáo", files, format_func=lambda p: p.stem)
        st.markdown(f.read_text(encoding="utf-8"))

with tab_chart:
    ticker = st.text_input("Mã", "PLTR").upper()
    df = cache.read_prices(ticker, date(2000, 1, 1), date.today())
    if df.empty:
        st.warning(f"Chưa có giá {ticker} trong cache. Chạy `uv run moneyflow fetch {ticker}`.")
    else:
        st.line_chart(df["close"].rename(ticker))
        st.bar_chart((df["close"] * df["volume"] / 1e6).rename("Dollar volume ($M)"))
        if not signals.empty:
            hist = signals[signals["ticker"] == ticker].set_index("run_date")["flow_score"]
            if not hist.empty:
                st.line_chart(pd.Series(hist, name="Flow score"))
