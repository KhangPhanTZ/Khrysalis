"""Chỉ báo kỹ thuật và dòng tiền. Input là DataFrame OHLCV (cột open/high/low/close/volume)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def dollar_volume(df: pd.DataFrame) -> pd.Series:
    return (df["close"] * df["volume"]).rename("dollar_volume")


def rvol(volume: pd.Series, window: int = 20) -> pd.Series:
    """Relative volume: volume hôm nay / trung bình `window` phiên *trước đó*."""
    base = volume.rolling(window, min_periods=window).mean().shift(1)
    return (volume / base.replace(0, np.nan)).rename("rvol")


def cmf(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Chaikin Money Flow, trong khoảng [-1, 1]."""
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    mfv = mfm.fillna(0.0) * df["volume"]
    vol_sum = df["volume"].rolling(window, min_periods=window).sum().replace(0, np.nan)
    return (mfv.rolling(window, min_periods=window).sum() / vol_sum).rename("cmf")


def mfi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Money Flow Index, trong khoảng [0, 100]."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw = tp * df["volume"]
    delta = tp.diff()
    pos = raw.where(delta > 0, 0.0).rolling(window, min_periods=window).sum()
    neg = raw.where(delta < 0, 0.0).rolling(window, min_periods=window).sum()
    out = 100 - 100 / (1 + pos / neg.replace(0, np.nan))
    # Không có dòng tiền âm trong cửa sổ -> MFI = 100
    out = out.where(~((neg == 0) & (pos > 0)), 100.0)
    return out.rename("mfi")


def relative_strength(close: pd.Series, bench_close: pd.Series, window: int) -> pd.Series:
    """Hiệu suất `window` phiên của mã trừ hiệu suất của benchmark (đơn vị: tỉ lệ)."""
    bench = bench_close.reindex(close.index).ffill()
    return (close.pct_change(window) - bench.pct_change(window)).rename(f"rs_{window}")


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean().rename(f"sma_{window}")


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """RSI kiểu Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    out = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    out = out.where(~((loss == 0) & (gain > 0)), 100.0)
    return out.rename("rsi")


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean().rename("atr")


def technical_snapshot(df: pd.DataFrame) -> dict[str, float | None]:
    """Các chỉ số kỹ thuật tại phiên cuối, làm tròn để đưa vào prompt/báo cáo."""
    close = df["close"]
    last = float(close.iloc[-1])

    def _last(s: pd.Series, nd: int = 2) -> float | None:
        v = s.iloc[-1] if len(s) else np.nan
        return None if pd.isna(v) else round(float(v), nd)

    high_52w = float(close.tail(252).max())
    return {
        "close": round(last, 2),
        "change_1d_pct": _last(close.pct_change() * 100),
        "change_5d_pct": _last(close.pct_change(5) * 100),
        "change_20d_pct": _last(close.pct_change(20) * 100),
        "sma_20": _last(sma(close, 20)),
        "sma_50": _last(sma(close, 50)),
        "sma_200": _last(sma(close, 200)),
        "rsi_14": _last(rsi(close, 14)),
        "atr_14": _last(atr(df, 14)),
        "pct_from_52w_high": round((last / high_52w - 1) * 100, 2),
    }
