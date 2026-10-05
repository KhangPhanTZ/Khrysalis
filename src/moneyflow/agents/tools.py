"""Tool = hàm Python có type hint. Agent chỉ được lấy số liệu thông qua các tool này.

Mọi output tool được ghi vào `ledger` để guardrail đối chiếu số liệu trong báo cáo.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from moneyflow.analytics.indicators import technical_snapshot
from moneyflow.analytics.risk import risk_snapshot
from moneyflow.data.edgar import EdgarClient
from moneyflow.data.finnhub import FinnhubClient

log = logging.getLogger(__name__)

# Chỉ số cơ bản Finnhub đưa vào prompt (bỏ bớt cho gọn context)
FUNDAMENTAL_KEYS = (
    "marketCapitalization",
    "peTTM",
    "psTTM",
    "pbQuarterly",
    "epsGrowthTTMYoy",
    "revenueGrowthTTMYoy",
    "grossMarginTTM",
    "operatingMarginTTM",
    "netProfitMarginTTM",
    "roeTTM",
    "totalDebt/totalEquityQuarterly",
    "52WeekHigh",
    "52WeekLow",
)


class Toolbox:
    def __init__(
        self,
        as_of: date,
        prices: dict[str, pd.DataFrame],
        bench_close: pd.Series,
        scores: pd.DataFrame,
        finnhub: FinnhubClient | None = None,
        edgar: EdgarClient | None = None,
    ) -> None:
        self.as_of = as_of
        self.prices = prices
        self.bench_close = bench_close
        self.scores = scores
        self.finnhub = finnhub
        self.edgar = edgar
        self.ledger: dict[str, dict[str, Any]] = {}

    def _log(self, tool: str, ticker: str, out: Any) -> Any:
        self.ledger.setdefault(ticker, {})[tool] = out
        return out

    def get_flow_score(self, ticker: str) -> dict[str, float]:
        row = self.scores.loc[ticker].astype(float)
        out = {str(k): round(float(v), 4) for k, v in row.to_dict().items()}
        out["universe_size"] = float(len(self.scores))
        return self._log("flow_score", ticker, out)  # type: ignore[no-any-return]

    def get_indicators(self, ticker: str) -> dict[str, float | None]:
        return self._log("indicators", ticker, technical_snapshot(self.prices[ticker]))  # type: ignore[no-any-return]

    def get_risk(self, ticker: str) -> dict[str, float | None]:
        out = risk_snapshot(self.prices[ticker], self.bench_close)
        return self._log("risk", ticker, out)  # type: ignore[no-any-return]

    def get_news(self, ticker: str, days: int = 7) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if self.finnhub is not None:
            try:
                items = self.finnhub.company_news(ticker, self.as_of, days)[:15]
            except Exception:
                log.exception("get_news %s lỗi", ticker)
        return self._log("news", ticker, items)  # type: ignore[no-any-return]

    def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        filings: list[dict[str, Any]] = []
        if self.finnhub is not None:
            try:
                raw = self.finnhub.basic_financials(ticker)
                metrics = {k: raw[k] for k in FUNDAMENTAL_KEYS if raw.get(k) is not None}
            except Exception:
                log.exception("get_fundamentals %s lỗi", ticker)
        if self.edgar is not None:
            try:
                filings = self.edgar.recent_filings(ticker, limit=5)
            except Exception:
                log.exception("get_filings %s lỗi", ticker)
        return self._log("fundamentals", ticker, {"metrics": metrics, "filings": filings})  # type: ignore[no-any-return]
