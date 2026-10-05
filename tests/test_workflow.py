from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest

from moneyflow.agents.screener import ScreenResult
from moneyflow.agents.tools import Toolbox
from moneyflow.analytics.flow_score import score_universe
from moneyflow.config import ScreenerConfig
from moneyflow.llm import schemas as s
from tests.conftest import make_ohlcv

pytest.importorskip("langgraph")


class FakeLLM:
    """Trả về schema cố định; lần gọi report đầu tiên cố tình bịa số để test vòng guardrail."""

    def __init__(self) -> None:
        self.report_calls = 0

    def structured(self, data: dict[str, Any], schema: type[Any], instruction: str = "") -> Any:
        t = data.get("ticker", "")
        if schema is s.TechnicalView:
            return s.TechnicalView(
                ticker=t,
                trend="uptrend",
                stance="bullish",
                confidence=0.7,
                key_points=[],
                summary="ok",
            )
        if schema is s.FundamentalView:
            return s.FundamentalView(
                ticker=t,
                valuation="unknown",
                quality="unknown",
                stance="neutral",
                key_points=[],
                summary="ok",
            )
        if schema is s.NewsView:
            return s.NewsView(
                ticker=t, sentiment="none", catalysts=[], source_urls=[], summary="ok"
            )
        if schema is s.RiskView:
            return s.RiskView(ticker=t, risk_level="medium", key_risks=[], summary="ok")
        self.report_calls += 1
        picks = [
            s.ReportPick(
                ticker=r["ticker"], stance="bullish", thesis="Dòng tiền mạnh", watch_for="Theo dõi"
            )
            for r in data["ranking"]
        ]
        overview = "Mục tiêu giá 987.65" if self.report_calls == 1 else "Dòng tiền lan rộng"
        return s.ReportNarrative(headline="Tóm tắt", market_overview=overview, picks=picks)


def test_pipeline_end_to_end_with_guardrail_retry() -> None:
    from moneyflow.graph.workflow import Agents, run_pipeline

    bench = make_ohlcv(seed=42)
    prices = {f"T{i}": make_ohlcv(seed=i, drift=0.001 * i) for i in range(5)}
    cfg = ScreenerConfig(min_avg_dollar_volume=0, top_n=3)
    scores = score_universe(prices, bench["close"], cfg)
    screen = ScreenResult(date(2026, 1, 2), scores, scores.head(3), prices, bench["close"])
    tools = Toolbox(screen.as_of, prices, bench["close"], scores)

    llm = FakeLLM()
    agents = Agents(llm, llm, llm, llm, llm)  # type: ignore[arg-type]
    state = run_pipeline(screen, tools, agents)

    assert llm.report_calls == 2  # lần 1 bị guardrail chặn, lần 2 hợp lệ
    assert state["guardrail"] is not None and state["guardrail"].ok
    md = state["report_markdown"]
    assert "# MoneyFlow daily — 2026-01-02" in md
    assert "987.65" not in md
    assert isinstance(scores, pd.DataFrame)
