"""Backtest tín hiệu screener: mỗi ngày mua đều top N theo flow score, giữ `hold` phiên.

So sánh với buy & hold QQQ. Dùng vectorbt nếu có (`uv sync --extra backtest`), không thì
tính lợi nhuận bằng pandas.

Chạy: `uv run python -m backtest.screener_backtest --start 2025-01-01 --end 2026-09-30`
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import pandas as pd

from moneyflow.analytics.flow_score import score_universe
from moneyflow.config import ScreenerConfig, get_settings, load_screener_config, load_universe
from moneyflow.data.cache import CachedProvider, PriceCache
from moneyflow.data.yfinance_provider import YFinanceProvider


def signal_matrix(
    prices: dict[str, pd.DataFrame],
    bench_close: pd.Series,
    cfg: ScreenerConfig,
    rebalance_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Ma trận bool (ngày x mã): True nếu mã nằm trong top N tại ngày đó (không nhìn trước)."""
    tickers = sorted(prices)
    sig = pd.DataFrame(False, index=rebalance_dates, columns=tickers)
    for d in rebalance_dates:
        scores = score_universe(prices, bench_close.loc[:d], cfg, as_of=d)
        sig.loc[d, list(scores.head(cfg.top_n).index)] = True
    return sig


def forward_returns(close: pd.DataFrame, hold: int) -> pd.DataFrame:
    """Lợi nhuận từ close hôm sau (vào lệnh T+1) tới close sau `hold` phiên."""
    entry = close.shift(-1)
    exit_ = close.shift(-(hold + 1))
    return exit_ / entry - 1


def evaluate(
    close: pd.DataFrame, bench_close: pd.Series, sig: pd.DataFrame, hold: int
) -> pd.DataFrame:
    fwd = forward_returns(close, hold).reindex(sig.index)
    bench_fwd = forward_returns(bench_close.to_frame("b"), hold)["b"].reindex(sig.index)
    picked = fwd.where(sig).mean(axis=1)
    universe = fwd.mean(axis=1)
    return pd.DataFrame({"top_n": picked, "universe_eq": universe, "benchmark": bench_fwd}).dropna()


def summarize(res: pd.DataFrame) -> pd.DataFrame:
    stats = pd.DataFrame(
        {
            "mean_fwd_return_%": res.mean() * 100,
            "hit_rate_vs_bench_%": [(res[c] > res["benchmark"]).mean() * 100 for c in res.columns],
            "n_obs": res.count(),
        }
    )
    return stats.round(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--hold", type=int, default=5, help="Số phiên nắm giữ")
    ap.add_argument("--every", type=int, default=5, help="Rebalance mỗi N phiên")
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    cfg = load_screener_config()
    uni = load_universe()
    provider = CachedProvider(YFinanceProvider(), PriceCache(get_settings().moneyflow_db_path))
    load_from = start - timedelta(days=int(cfg.lookback_days * 1.5))
    bench = provider.get_prices(uni.benchmark, load_from, end)["close"]
    prices = provider.get_many(uni.tickers, load_from, end)

    close = pd.DataFrame({t: df["close"] for t, df in prices.items()}).reindex(bench.index)
    days = bench.loc[pd.Timestamp(start) :].index[:: args.every]
    sig = signal_matrix(prices, bench, cfg, pd.DatetimeIndex(days))
    res = evaluate(close, bench, sig, args.hold)
    print(summarize(res).to_string())

    try:
        import vectorbt as vbt

        entries = sig.reindex(close.index, fill_value=False)
        exits = entries.shift(args.hold, fill_value=False)
        pf = vbt.Portfolio.from_signals(close[entries.columns], entries, exits, freq="1D")
        print(f"vectorbt — total return trung bình mỗi mã: {pf.total_return().mean():.2%}")
    except ImportError:
        print("(cài `uv sync --extra backtest` để có thống kê vectorbt)")


if __name__ == "__main__":
    main()
