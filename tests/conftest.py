from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(
    n: int = 300,
    start_price: float = 100.0,
    drift: float = 0.0,
    vol: float = 0.01,
    base_volume: float = 2_000_000,
    volume_trend: float = 0.0,
    close_pos: float = 0.5,
    seed: int = 0,
) -> pd.DataFrame:
    """Giá giả lập. `close_pos` ∈ [0,1]: vị trí close trong range high-low (1 = đóng cửa ở đỉnh)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-01-01", periods=n, name="date")
    rets = drift + vol * rng.standard_normal(n)
    close = start_price * np.exp(np.cumsum(rets))
    spread = close * 0.02
    low = close - spread * close_pos
    high = low + spread
    open_ = (high + low) / 2
    volume = base_volume * (1 + volume_trend) ** np.arange(n) * (1 + 0.1 * rng.random(n))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx
    )


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return make_ohlcv()


@pytest.fixture
def bench() -> pd.DataFrame:
    return make_ohlcv(seed=42, drift=0.0003, base_volume=50_000_000)
