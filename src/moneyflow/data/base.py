"""Interface DataProvider — mọi nguồn giá (yfinance, Polygon, FMP…) đều implement nó."""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@runtime_checkable
class DataProvider(Protocol):
    """Nguồn giá OHLCV ngày.

    `get_prices` trả về DataFrame index là `DatetimeIndex` (tên `date`, đã sort tăng dần),
    cột đúng như `OHLCV_COLUMNS`. Mã không có dữ liệu trả về DataFrame rỗng.
    """

    name: str

    def get_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...


def empty_ohlcv() -> pd.DataFrame:
    df = pd.DataFrame(columns=OHLCV_COLUMNS, dtype="float64")
    df.index = pd.DatetimeIndex([], name="date")
    return df


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hoá tên cột/thứ tự/kiểu dữ liệu về schema OHLCV."""
    if df.empty:
        return empty_ohlcv()
    out = df.rename(columns=str.lower)
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"Thiếu cột {missing}")
    out = out[OHLCV_COLUMNS].astype("float64")
    idx = pd.DatetimeIndex(pd.to_datetime(out.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize().rename("date")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(subset=["close"])
