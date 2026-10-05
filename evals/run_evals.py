"""Chạy analyst agents trên golden set và chấm độ chính xác số liệu + độ bám nguồn tin."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from moneyflow.agents.screener import run_screen
from moneyflow.agents.tools import Toolbox
from moneyflow.config import get_settings, load_screener_config, load_universe
from moneyflow.data.cache import CachedProvider, PriceCache
from moneyflow.data.finnhub import FinnhubClient
from moneyflow.data.yfinance_provider import YFinanceProvider
from moneyflow.graph.workflow import Agents, analyze_ticker
from moneyflow.llm.client import get_llm
from moneyflow.llm.cost import CostTracker
from moneyflow.llm.guardrail import check_numbers

EVAL_DIR = Path(__file__).parent


def score_case(analysis: Any, ledger: dict[str, Any]) -> dict[str, Any]:
    texts = []
    for view in (analysis.technical, analysis.fundamental, analysis.news, analysis.risk):
        if view is not None:
            texts.append(view.summary)
            texts.extend(getattr(view, "key_points", []) or [])
            texts.extend(getattr(view, "key_risks", []) or [])
            texts.extend(getattr(view, "catalysts", []) or [])
    numbers = check_numbers("\n".join(texts), [ledger])
    known_urls = {n.get("url") for n in ledger.get("news", [])}
    urls = analysis.news.source_urls if analysis.news else []
    grounded = [u for u in urls if u in known_urls]
    return {
        "numbers_ok": numbers.ok,
        "numbers_checked": numbers.checked,
        "unsupported": numbers.unsupported,
        "url_grounding": (len(grounded) / len(urls)) if urls else 1.0,
        "errors": analysis.errors,
    }


def main() -> None:
    settings = get_settings()
    cases = yaml.safe_load((EVAL_DIR / "golden.yaml").read_text())["cases"]
    provider = CachedProvider(YFinanceProvider(), PriceCache(settings.moneyflow_db_path))
    tracker = CostTracker()
    agents = Agents(
        **{
            r: get_llm(r, settings, tracker)
            for r in ("technical", "fundamental", "news", "risk", "report")  # type: ignore[arg-type]
        }
    )
    finnhub = FinnhubClient(settings.finnhub_key) if settings.finnhub_key else None

    results = []
    by_date: dict[date, list[str]] = {}
    for c in cases:
        by_date.setdefault(c["date"], []).append(c["ticker"])
    for d, tickers in by_date.items():
        screen = run_screen(provider, load_universe(), load_screener_config(), d)
        tools = Toolbox(d, screen.prices, screen.bench_close, screen.scores, finnhub=finnhub)
        for t in tickers:
            if t not in screen.scores.index:
                results.append({"date": str(d), "ticker": t, "skipped": "không có trong universe"})
                continue
            a = analyze_ticker(t, tools, agents)
            results.append({"date": str(d), "ticker": t, **score_case(a, tools.ledger.get(t, {}))})

    scored = [r for r in results if "skipped" not in r]
    summary = {
        "cases": len(scored),
        "numeric_accuracy": sum(r["numbers_ok"] for r in scored) / max(len(scored), 1),
        "url_grounding": sum(r["url_grounding"] for r in scored) / max(len(scored), 1),
        "cost": tracker.summary(),
    }
    out = EVAL_DIR / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2, default=str))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
