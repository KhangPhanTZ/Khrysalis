from __future__ import annotations

import pandas as pd
import pytest

from moneyflow.analytics import indicators as ind
from tests.conftest import make_ohlcv


def test_dollar_volume(ohlcv: pd.DataFrame) -> None:
    dv = ind.dollar_volume(ohlcv)
    assert dv.iloc[-1] == pytest.approx(ohlcv["close"].iloc[-1] * ohlcv["volume"].iloc[-1])


def test_rvol_uses_previous_window() -> None:
    vol = pd.Series([100.0] * 20 + [300.0])
    r = ind.rvol(vol, window=20)
    assert r.iloc[-1] == pytest.approx(3.0)
    assert r.iloc[:20].isna().all()


def test_cmf_extremes() -> None:
    at_high = make_ohlcv(n=60, close_pos=1.0)
    at_low = make_ohlcv(n=60, close_pos=0.0)
    assert ind.cmf(at_high).iloc[-1] == pytest.approx(1.0)
    assert ind.cmf(at_low).iloc[-1] == pytest.approx(-1.0)


def test_mfi_and_rsi_bounds(ohlcv: pd.DataFrame) -> None:
    m = ind.mfi(ohlcv).dropna()
    r = ind.rsi(ohlcv["close"]).dropna()
    assert ((m >= 0) & (m <= 100)).all()
    assert ((r >= 0) & (r <= 100)).all()


def test_mfi_all_up_is_100() -> None:
    df = make_ohlcv(n=40, drift=0.01, vol=0.0)
    assert ind.mfi(df).iloc[-1] == pytest.approx(100.0)


def test_relative_strength() -> None:
    idx = pd.bdate_range("2025-01-01", periods=3)
    stock = pd.Series([100.0, 105.0, 110.0], index=idx)
    bench = pd.Series([100.0, 101.0, 102.0], index=idx)
    rs = ind.relative_strength(stock, bench, window=2)
    assert rs.iloc[-1] == pytest.approx(0.10 - 0.02)


def test_technical_snapshot_keys(ohlcv: pd.DataFrame) -> None:
    snap = ind.technical_snapshot(ohlcv)
    assert snap["close"] == round(float(ohlcv["close"].iloc[-1]), 2)
    assert snap["sma_200"] is not None
    assert snap["pct_from_52w_high"] is not None and snap["pct_from_52w_high"] <= 0
