"""Screener agent — thuần code, không dùng LLM: tải giá, tính điểm dòng tiền, lấy top N."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from moneyflow.analytics.flow_score import score_universe
from moneyflow.config import ScreenerConfig, Universe
from moneyflow.data.cache import CachedProvider

log = logging.getLogger(__name__)


@dataclass
class ScreenResult:
    as_of: date
    scores: pd.DataFrame  # toàn bộ universe đã chấm điểm
    top: pd.DataFrame  # top N
    prices: dict[str, pd.DataFrame]
    bench_close: pd.Series


def run_screen(
    provider: CachedProvider, universe: Universe, cfg: ScreenerConfig, as_of: date
) -> ScreenResult:
    # lookback tính theo phiên -> đổi sang ngày lịch (≈ 1.5x) cho dư
    start = as_of - timedelta(days=int(cfg.lookback_days * 1.5))
    bench = provider.get_prices(universe.benchmark, start, as_of)
    if bench.empty:
        raise RuntimeError(f"Không tải được benchmark {universe.benchmark}")
    prices = provider.get_many(universe.tickers, start, as_of)
    log.info("Đã có giá cho %d/%d mã", len(prices), len(universe.tickers))

    scores = score_universe(prices, bench["close"], cfg, as_of=pd.Timestamp(as_of))
    return ScreenResult(
        as_of=as_of,
        scores=scores,
        top=scores.head(cfg.top_n),
        prices=prices,
        bench_close=bench["close"],
    )
