"""Tin tức và chỉ số cơ bản từ Finnhub (free tier)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import requests

BASE_URL = "https://finnhub.io/api/v1"


class FinnhubClient:
    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("Thiếu FINNHUB_KEY")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, str]) -> Any:
        resp = self.session.get(
            f"{BASE_URL}{path}", params={**params, "token": self.api_key}, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def company_news(self, ticker: str, as_of: date, days: int = 7) -> list[dict[str, Any]]:
        params = {
            "symbol": ticker,
            "from": (as_of - timedelta(days=days)).isoformat(),
            "to": as_of.isoformat(),
        }
        items = self._get("/company-news", params)
        return [
            {
                "datetime": i.get("datetime"),
                "headline": i.get("headline", ""),
                "summary": i.get("summary", ""),
                "source": i.get("source", ""),
                "url": i.get("url", ""),
            }
            for i in (items or [])
        ]

    def basic_financials(self, ticker: str) -> dict[str, Any]:
        data = self._get("/stock/metric", {"symbol": ticker, "metric": "all"})
        metric: dict[str, Any] = (data or {}).get("metric", {})
        return metric
