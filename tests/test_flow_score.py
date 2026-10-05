from __future__ import annotations

import pandas as pd

from moneyflow.analytics.flow_score import score_universe
from moneyflow.analytics.risk import beta, max_drawdown, risk_snapshot
from moneyflow.config import ScreenerConfig
from tests.conftest import make_ohlcv


def _universe() -> dict[str, pd.DataFrame]:
    return {
        # dòng tiền mạnh: giá tăng, đóng cửa gần đỉnh, volume tăng dần
        "STRONG": make_ohlcv(seed=1, drift=0.004, vol=0.003, close_pos=0.9, volume_trend=0.01),
        "FLAT": make_ohlcv(seed=2, vol=0.003),
        "WEAK": make_ohlcv(seed=3, drift=-0.003, vol=0.003, close_pos=0.1),
        "ILLIQ": make_ohlcv(seed=4, drift=0.004, close_pos=0.9, base_volume=1_000),
    }


def test_strong_ranks_first_and_illiquid_filtered(bench: pd.DataFrame) -> None:
    cfg = ScreenerConfig(min_avg_dollar_volume=10_000_000)
    scores = score_universe(_universe(), bench["close"], cfg)
    assert "ILLIQ" not in scores.index
    assert scores.index[0] == "STRONG"
    assert scores.index[-1] == "WEAK"
    assert list(scores["rank"]) == [1, 2, 3]
    assert scores["flow_score"].between(0, 100).all()


def test_as_of_cuts_future(bench: pd.DataFrame) -> None:
    cfg = ScreenerConfig(min_avg_dollar_volume=0)
    uni = _universe()
    as_of = uni["FLAT"].index[200]
    scores = score_universe(uni, bench["close"], cfg, as_of=as_of)
    assert scores.loc["FLAT", "close"] == uni["FLAT"]["close"].iloc[200]


def test_insufficient_history_dropped(bench: pd.DataFrame) -> None:
    cfg = ScreenerConfig(min_avg_dollar_volume=0)
    scores = score_universe({"NEW": make_ohlcv(n=30)}, bench["close"], cfg)
    assert scores.empty


def test_risk_metrics(ohlcv: pd.DataFrame) -> None:
    assert max_drawdown(ohlcv["close"]) <= 0
    assert abs(beta(ohlcv["close"], ohlcv["close"]) - 1.0) < 1e-9
    snap = risk_snapshot(ohlcv, ohlcv["close"])
    assert snap["volatility_60d_pct"] is not None and snap["volatility_60d_pct"] > 0
