"""SEC EDGAR: danh sách filing gần đây (10-K, 10-Q, 8-K) của một mã."""

from __future__ import annotations

from functools import cached_property
from typing import Any

import requests

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


class EdgarClient:
    def __init__(self, user_agent: str, timeout: float = 15.0) -> None:
        # SEC yêu cầu User-Agent có thông tin liên hệ
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.timeout = timeout

    @cached_property
    def _cik_map(self) -> dict[str, int]:
        resp = self.session.get(TICKERS_URL, timeout=self.timeout)
        resp.raise_for_status()
        return {v["ticker"].upper(): int(v["cik_str"]) for v in resp.json().values()}

    def recent_filings(
        self, ticker: str, forms: tuple[str, ...] = ("10-K", "10-Q", "8-K"), limit: int = 10
    ) -> list[dict[str, Any]]:
        cik = self._cik_map.get(ticker.upper())
        if cik is None:
            return []
        resp = self.session.get(SUBMISSIONS_URL.format(cik=cik), timeout=self.timeout)
        resp.raise_for_status()
        recent = resp.json().get("filings", {}).get("recent", {})
        out: list[dict[str, Any]] = []
        for form, filed, acc, doc in zip(
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
            strict=False,
        ):
            if form in forms:
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
                out.append({"form": form, "filed": filed, "url": url})
            if len(out) >= limit:
                break
        return out
