"""Chỉ số rủi ro thuần: biến động, drawdown, beta so với benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def annualized_volatility(close: pd.Series, window: int = 60) -> float:
    r = close.pct_change().dropna().tail(window)
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(r) > 1 else float("nan")


def max_drawdown(close: pd.Series, window: int = 252) -> float:
    """Drawdown sâu nhất trong `window` phiên (số âm, đơn vị tỉ lệ)."""
    c = close.tail(window)
    return float((c / c.cummax() - 1).min())


def beta(close: pd.Series, bench_close: pd.Series, window: int = 120) -> float:
    df = pd.concat([close.pct_change(), bench_close.pct_change()], axis=1, join="inner")
    df = df.dropna().tail(window)
    if len(df) < 2:
        return float("nan")
    x = df.iloc[:, 0].to_numpy(dtype=float)
    y = df.iloc[:, 1].to_numpy(dtype=float)
    var = float(np.var(y, ddof=1))
    return float(np.cov(x, y, ddof=1)[0, 1] / var) if var > 0 else float("nan")


def risk_snapshot(df: pd.DataFrame, bench_close: pd.Series) -> dict[str, float | None]:
    close = df["close"]

    def _r(v: float, nd: int = 2) -> float | None:
        return None if np.isnan(v) else round(v, nd)

    atr_pct = (
        (df["high"] - df["low"]).tail(14).mean() / float(close.iloc[-1]) * 100
        if len(df) >= 14
        else float("nan")
    )
    return {
        "volatility_60d_pct": _r(annualized_volatility(close) * 100),
        "max_drawdown_1y_pct": _r(max_drawdown(close) * 100),
        "beta_120d": _r(beta(close, bench_close)),
        "avg_range_14d_pct": _r(float(atr_pct)),
    }
