"""DataProvider dùng yfinance (miễn phí, cho giai đoạn prototype)."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from moneyflow.data.base import empty_ohlcv, normalize_ohlcv

log = logging.getLogger(__name__)


class YFinanceProvider:
    name = "yfinance"

    def get_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        import yfinance as yf

        # yfinance coi `end` là exclusive
        raw = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        if raw is None or raw.empty:
            log.warning("yfinance: không có dữ liệu cho %s", ticker)
            return empty_ohlcv()
        return normalize_ohlcv(raw)
