from __future__ import annotations

from datetime import date

import pandas as pd

from moneyflow.config import load_screener_config, load_universe
from moneyflow.llm.guardrail import GuardrailResult
from moneyflow.llm.schemas import ReportNarrative, ReportPick, TickerAnalysis
from moneyflow.notify import split_message
from moneyflow.reports.markdown import render_report, render_screen_only


def _top() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rank": [1],
            "flow_score": [91.2],
            "close": [182.5],
            "dollar_volume": [2.4e9],
            "rvol": [2.1],
            "cmf": [0.31],
            "mfi": [72.0],
            "rs_short": [0.081],
        },
        index=pd.Index(["PLTR"], name="ticker"),
    )


def test_screen_table() -> None:
    md = render_screen_only(date(2026, 10, 5), _top(), 100)
    assert "| 1 | **PLTR** | 91.2 | 182.50 | $2.40B | 2.10 | 0.31 | 72 | +8.1% |" in md


def test_full_report_flags_guardrail() -> None:
    narrative = ReportNarrative(
        headline="Dòng tiền tập trung vào phần mềm AI",
        market_overview="...",
        picks=[
            ReportPick(ticker="PLTR", stance="bullish", thesis="RVOL 2.1", watch_for="Mất SMA 20")
        ],
    )
    md = render_report(
        date(2026, 10, 5),
        _top(),
        100,
        [TickerAnalysis(ticker="PLTR")],
        narrative,
        GuardrailResult(ok=False, checked=1, unsupported=["999"]),
    )
    assert "### PLTR — bullish" in md
    assert "Guardrail" in md and "999" in md


def test_split_message() -> None:
    text = "\n\n".join(["a" * 1500] * 5)
    chunks = split_message(text, limit=4000)
    assert all(len(c) <= 4000 for c in chunks)
    assert "\n\n".join(chunks) == text


def test_config_files_load() -> None:
    uni = load_universe()
    cfg = load_screener_config()
    assert uni.benchmark == "QQQ"
    assert "PLTR" in uni.tickers and "QQQ" not in uni.tickers
    assert len(uni.tickers) == len(set(uni.tickers))
    assert abs(sum(cfg.weights.values()) - 1.0) < 1e-9
