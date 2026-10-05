from __future__ import annotations

from datetime import date

import pandas as pd

from moneyflow.data.cache import CachedProvider, PriceCache
from tests.conftest import make_ohlcv


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.full = make_ohlcv(n=300)
        self.calls: list[tuple[str, date, date]] = []

    def get_prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        self.calls.append((ticker, start, end))
        return self.full.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def test_second_call_hits_cache() -> None:
    fake = FakeProvider()
    provider = CachedProvider(fake, PriceCache())
    start, end = date(2025, 1, 1), date(2025, 6, 30)

    first = provider.get_prices("pltr", start, end)
    second = provider.get_prices("PLTR", start, end)

    assert len(fake.calls) == 1
    assert not first.empty
    pd.testing.assert_frame_equal(first, second)


def test_only_missing_range_is_fetched() -> None:
    fake = FakeProvider()
    provider = CachedProvider(fake, PriceCache())
    provider.get_prices("QQQ", date(2025, 3, 1), date(2025, 6, 30))
    provider.get_prices("QQQ", date(2025, 1, 1), date(2025, 8, 31))
    assert fake.calls[1:] == [
        ("QQQ", date(2025, 1, 1), date(2025, 2, 28)),
        ("QQQ", date(2025, 7, 1), date(2025, 8, 31)),
    ]


def test_signals_roundtrip() -> None:
    cache = PriceCache()
    scores = pd.DataFrame(
        {"flow_score": [80.0, 60.0], "rank": [1, 2]}, index=pd.Index(["A", "B"], name="ticker")
    )
    cache.write_signals(date(2026, 1, 2), scores)
    cache.write_signals(date(2026, 1, 2), scores)  # ghi lại cùng ngày không nhân đôi
    out = cache.read_signals()
    assert list(out["ticker"]) == ["A", "B"]
