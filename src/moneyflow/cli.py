"""CLI: `moneyflow fetch`, `moneyflow screen`, `moneyflow run`."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from moneyflow.config import get_settings, load_screener_config, load_universe
from moneyflow.data.cache import CachedProvider, PriceCache
from moneyflow.data.yfinance_provider import YFinanceProvider

app = typer.Typer(
    help="MoneyFlow Agents — screen cổ phiếu Mỹ theo dòng tiền.", no_args_is_help=True
)

DateOpt = Annotated[str, typer.Option("--date", "-d", help="YYYY-MM-DD hoặc 'today'")]


def _parse_date(value: str) -> date:
    if value.lower() == "today":
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def _provider() -> tuple[CachedProvider, PriceCache]:
    cache = PriceCache(get_settings().moneyflow_db_path)
    return CachedProvider(YFinanceProvider(), cache), cache


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def fetch(
    tickers: Annotated[list[str], typer.Argument(help="Ví dụ: QQQ PLTR")],
    days: Annotated[int, typer.Option(help="Số ngày lịch sử")] = 365,
    as_of: DateOpt = "today",
) -> None:
    """Tải giá vào cache DuckDB (lần chạy thứ hai lấy từ cache)."""
    end = _parse_date(as_of)
    provider, cache = _provider()
    for t in tickers:
        df = provider.get_prices(t, end - timedelta(days=days), end)
        span = f"{df.index[0].date()} → {df.index[-1].date()}" if not df.empty else "trống"
        typer.echo(f"{t.upper():6s} {len(df):4d} phiên  {span}")
    typer.echo(f"Gọi mạng: {provider.network_calls} lần")
    cache.close()


@app.command()
def screen(
    as_of: DateOpt = "today",
    top: Annotated[int | None, typer.Option(help="Ghi đè top_n trong screener.yaml")] = None,
    out: Annotated[Path | None, typer.Option(help="Ghi Markdown ra file")] = None,
) -> None:
    """Chạy screener dòng tiền (không cần LLM) và in top N kèm điểm."""
    from moneyflow.agents.screener import run_screen
    from moneyflow.reports.markdown import render_screen_only

    cfg = load_screener_config()
    if top:
        cfg.top_n = top
    provider, cache = _provider()
    d = _parse_date(as_of)
    result = run_screen(provider, load_universe(), cfg, d)
    cache.write_signals(d, result.scores)
    md = render_screen_only(d, result.top, len(result.scores))
    typer.echo(md)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    cache.close()


@app.command()
def run(
    as_of: DateOpt = "today",
    out_dir: Annotated[Path, typer.Option(help="Thư mục lưu báo cáo")] = Path("reports_out"),
    telegram: Annotated[bool, typer.Option(help="Gửi báo cáo qua Telegram")] = False,
) -> None:
    """Pipeline đầy đủ: screener -> 4 analyst agent -> report agent -> guardrail -> Markdown."""
    from moneyflow.agents.screener import run_screen
    from moneyflow.agents.tools import Toolbox
    from moneyflow.data.edgar import EdgarClient
    from moneyflow.data.finnhub import FinnhubClient
    from moneyflow.graph.workflow import Agents, run_pipeline
    from moneyflow.llm.client import get_llm
    from moneyflow.llm.cost import CostTracker

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise typer.BadParameter("Thiếu ANTHROPIC_API_KEY (xem .env.example)")

    d = _parse_date(as_of)
    provider, cache = _provider()
    result = run_screen(provider, load_universe(), load_screener_config(), d)
    cache.write_signals(d, result.scores)

    tools = Toolbox(
        as_of=d,
        prices=result.prices,
        bench_close=result.bench_close,
        scores=result.scores,
        finnhub=FinnhubClient(settings.finnhub_key) if settings.finnhub_key else None,
        edgar=EdgarClient(settings.sec_user_agent),
    )
    tracker = CostTracker()
    llm_cache = settings.moneyflow_db_path.parent / "llm_cache"
    agents = Agents(
        technical=get_llm("technical", settings, tracker, cache_dir=llm_cache),
        fundamental=get_llm("fundamental", settings, tracker, cache_dir=llm_cache),
        news=get_llm("news", settings, tracker, cache_dir=llm_cache),
        risk=get_llm("risk", settings, tracker, cache_dir=llm_cache),
        report=get_llm("report", settings, tracker, cache_dir=llm_cache),
    )
    state = run_pipeline(result, tools, agents)
    md = state.get("report_markdown", "")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{d.isoformat()}.md"
    path.write_text(md, encoding="utf-8")
    typer.echo(md)
    typer.echo(f"\nĐã lưu {path}. Chi phí LLM: {tracker.summary()}", err=True)

    if telegram:
        from moneyflow.notify import send_telegram

        send_telegram(md, settings)
    cache.close()


if __name__ == "__main__":
    app()
