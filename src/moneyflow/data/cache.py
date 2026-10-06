"""Cache giá OHLCV và lịch sử tín hiệu trong DuckDB."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from moneyflow.data.base import OHLCV_COLUMNS, DataProvider, empty_ohlcv, normalize_ohlcv

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker VARCHAR NOT NULL,
    date DATE NOT NULL,
    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
    source VARCHAR,
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    ticker VARCHAR PRIMARY KEY,
    first_date DATE,
    last_date DATE
);
CREATE TABLE IF NOT EXISTS signals (
    run_date DATE NOT NULL,
    ticker VARCHAR NOT NULL,
    rank INTEGER,
    flow_score DOUBLE,
    payload JSON,
    PRIMARY KEY (run_date, ticker)
);
"""


class PriceCache:
    """Kho DuckDB. Dùng `:memory:` cho test."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(_SCHEMA)

    def close(self) -> None:
        self.con.close()

    # --- prices ---------------------------------------------------------
    def write_prices(self, ticker: str, df: pd.DataFrame, source: str) -> int:
        if df.empty:
            return 0
        frame = df[OHLCV_COLUMNS].copy()
        frame.insert(0, "date", pd.DatetimeIndex(frame.index).date)
        frame.insert(0, "ticker", ticker)
        frame["source"] = source
        self.con.register("_incoming", frame.reset_index(drop=True))
        self.con.execute("INSERT OR REPLACE INTO prices SELECT * FROM _incoming")
        self.con.unregister("_incoming")
        return len(frame)

    def read_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        df = self.con.execute(
            "SELECT date, open, high, low, close, volume FROM prices "
            "WHERE ticker = ? AND date BETWEEN ? AND ? ORDER BY date",
            [ticker, start, end],
        ).df()
        if df.empty:
            return empty_ohlcv()
        return normalize_ohlcv(df.set_index("date"))

    def coverage(self, ticker: str) -> tuple[date, date] | None:
        row = self.con.execute(
            "SELECT first_date, last_date FROM fetch_log WHERE ticker = ?", [ticker]
        ).fetchone()
        return (row[0], row[1]) if row else None

    def mark_fetched(self, ticker: str, start: date, end: date) -> None:
        cov = self.coverage(ticker)
        if cov:
            start, end = min(start, cov[0]), max(end, cov[1])
        self.con.execute("INSERT OR REPLACE INTO fetch_log VALUES (?, ?, ?)", [ticker, start, end])

    # --- signals --------------------------------------------------------
    def write_signals(self, run_date: date, scores: pd.DataFrame) -> None:
        """Lưu kết quả screener (index = ticker, có cột rank, flow_score)."""
        self.con.execute("DELETE FROM signals WHERE run_date = ?", [run_date])
        rows = [
            (run_date, str(t), int(r["rank"]), float(r["flow_score"]), r.to_json())
            for t, r in scores.iterrows()
        ]
        if rows:
            self.con.executemany("INSERT INTO signals VALUES (?, ?, ?, ?, ?)", rows)

    def read_signals(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        sql = "SELECT run_date, ticker, rank, flow_score FROM signals"
        params: list[date] = []
        if start and end:
            sql += " WHERE run_date BETWEEN ? AND ?"
            params = [start, end]
        return self.con.execute(sql + " ORDER BY run_date, rank", params).df()


class CachedProvider:
    """Bọc một DataProvider: chỉ gọi mạng cho khoảng ngày chưa có trong cache."""

    def __init__(self, provider: DataProvider, cache: PriceCache) -> None:
        self.provider = provider
        self.cache = cache
        self.name = f"cached:{provider.name}"
        self.network_calls = 0

    def get_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        ticker = ticker.upper()
        for gap_start, gap_end in self._gaps(ticker, start, end):
            self.network_calls += 1
            try:
                df = self.provider.get_prices(ticker, gap_start, gap_end)
            except Exception:  # mạng/nguồn lỗi: bỏ qua mã này, không làm hỏng cả batch
                log.exception("Lỗi tải %s từ %s", ticker, self.provider.name)
                continue
            self.cache.write_prices(ticker, df, self.provider.name)
            self.cache.mark_fetched(ticker, gap_start, gap_end)
        return self.cache.read_prices(ticker, start, end)

    def get_many(self, tickers: Iterable[str], start: date, end: date) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for t in tickers:
            df = self.get_prices(t, start, end)
            if not df.empty:
                out[t.upper()] = df
        return out

    def _gaps(self, ticker: str, start: date, end: date) -> list[tuple[date, date]]:
        cov = self.cache.coverage(ticker)
        if cov is None:
            return [(start, end)]
        first, last = cov
        gaps: list[tuple[date, date]] = []
        if start < first:
            gaps.append((start, first - timedelta(days=1)))
        if end > last:
            gaps.append((last + timedelta(days=1), end))
        return gaps
