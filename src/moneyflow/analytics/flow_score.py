"""Điểm dòng tiền: xếp hạng percentile chéo các thành phần rồi lấy trung bình có trọng số."""

from __future__ import annotations

import numpy as np
import pandas as pd

from moneyflow.analytics import indicators as ind
from moneyflow.config import ScreenerConfig

COMPONENTS = ("dollar_volume", "rvol", "cmf", "mfi", "rs_short", "rs_long")


def flow_metrics(
    df: pd.DataFrame, bench_close: pd.Series, cfg: ScreenerConfig
) -> dict[str, float] | None:
    """Các thành phần dòng tiền của một mã tại phiên cuối. None nếu không đủ lịch sử."""
    w = cfg.windows
    need = max(w.avg_volume + w.rvol_smooth, w.cmf, w.mfi + 1, w.rs_long + 1)
    if len(df) < need:
        return None

    dv = ind.dollar_volume(df)
    metrics = {
        "close": float(df["close"].iloc[-1]),
        "dollar_volume": float(dv.tail(w.avg_volume).mean()),
        "rvol": float(ind.rvol(df["volume"], w.avg_volume).tail(w.rvol_smooth).mean()),
        "cmf": float(ind.cmf(df, w.cmf).iloc[-1]),
        "mfi": float(ind.mfi(df, w.mfi).iloc[-1]),
        "rs_short": float(ind.relative_strength(df["close"], bench_close, w.rs_short).iloc[-1]),
        "rs_long": float(ind.relative_strength(df["close"], bench_close, w.rs_long).iloc[-1]),
    }
    if any(np.isnan(v) for v in metrics.values()):
        return None
    return metrics


def score_universe(
    prices: dict[str, pd.DataFrame],
    bench_close: pd.Series,
    cfg: ScreenerConfig,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Tính điểm dòng tiền cho cả universe.

    Trả về DataFrame (index = ticker) gồm các thành phần thô, điểm percentile từng thành phần
    (`*_pct`, 0–100), `flow_score` (0–100) và `rank` (1 = mạnh nhất). Mã dưới ngưỡng
    `min_avg_dollar_volume` hoặc thiếu dữ liệu bị loại.
    """
    rows: dict[str, dict[str, float]] = {}
    for ticker, df in prices.items():
        if as_of is not None:
            df = df.loc[:as_of]
        m = flow_metrics(df, bench_close, cfg)
        if m is not None and m["dollar_volume"] >= cfg.min_avg_dollar_volume:
            rows[ticker] = m

    cols = ["close", *COMPONENTS]
    table = pd.DataFrame.from_dict(rows, orient="index", columns=cols)
    if table.empty:
        return table.assign(flow_score=pd.Series(dtype=float), rank=pd.Series(dtype=int))

    total_w = sum(cfg.weights.get(c, 0.0) for c in COMPONENTS)
    if total_w <= 0:
        raise ValueError("Tổng trọng số screener phải > 0")

    score = pd.Series(0.0, index=table.index)
    for c in COMPONENTS:
        pct = table[c].rank(pct=True) * 100
        table[f"{c}_pct"] = pct.round(1)
        score += pct * cfg.weights.get(c, 0.0) / total_w

    table["flow_score"] = score.round(1)
    table = table.sort_values(["flow_score", "dollar_volume"], ascending=False)
    table["rank"] = np.arange(1, len(table) + 1)
    table.index.name = "ticker"
    return table


def top_n(scores: pd.DataFrame, n: int) -> pd.DataFrame:
    return scores.head(n)
