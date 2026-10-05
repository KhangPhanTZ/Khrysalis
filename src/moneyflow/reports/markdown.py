"""Template Markdown. Bảng số liệu do code chèn; LLM chỉ viết phần diễn giải."""

from __future__ import annotations

from datetime import date

import pandas as pd

from moneyflow.llm.guardrail import GuardrailResult
from moneyflow.llm.schemas import ReportNarrative, TickerAnalysis

DISCLAIMER = "_Hệ thống chỉ hỗ trợ phân tích, không phải khuyến nghị đầu tư._"


def _fmt_money(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    return f"${v / 1e6:.0f}M"


def render_screen_table(top: pd.DataFrame) -> str:
    lines = [
        "| # | Mã | Điểm | Giá | Dollar vol 20d | RVOL | CMF | MFI | RS 20d vs QQQ |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for ticker, r in top.iterrows():
        lines.append(
            f"| {int(r['rank'])} | **{ticker}** | {r['flow_score']:.1f} | {r['close']:.2f} | "
            f"{_fmt_money(r['dollar_volume'])} | {r['rvol']:.2f} | {r['cmf']:.2f} | "
            f"{r['mfi']:.0f} | {r['rs_short'] * 100:+.1f}% |"
        )
    return "\n".join(lines)


def narrative_text(n: ReportNarrative) -> str:
    """Toàn bộ văn bản do LLM viết — đầu vào cho guardrail."""
    parts = [n.headline, n.market_overview]
    for p in n.picks:
        parts += [p.thesis, p.watch_for]
    return "\n".join(parts)


def render_screen_only(as_of: date, top: pd.DataFrame, universe_size: int) -> str:
    return "\n\n".join(
        [
            f"# MoneyFlow screener — {as_of.isoformat()}",
            f"Top {len(top)} / {universe_size} mã đủ thanh khoản, xếp theo điểm dòng tiền.",
            render_screen_table(top),
            DISCLAIMER,
        ]
    )


def render_report(
    as_of: date,
    top: pd.DataFrame,
    universe_size: int,
    analyses: list[TickerAnalysis],
    narrative: ReportNarrative | None,
    guardrail: GuardrailResult | None,
) -> str:
    out = [f"# MoneyFlow daily — {as_of.isoformat()}"]
    if narrative is not None:
        out += [f"> {narrative.headline}", "## Tổng quan", narrative.market_overview]
    out += [
        "## Bảng dòng tiền",
        f"Top {len(top)} / {universe_size} mã đủ thanh khoản.",
        render_screen_table(top),
    ]

    by_ticker = {a.ticker: a for a in analyses}
    picks = narrative.picks if narrative else []
    if picks:
        out.append("## Phân tích từng mã")
    for p in picks:
        a = by_ticker.get(p.ticker)
        section = [f"### {p.ticker} — {p.stance}", p.thesis, f"**Theo dõi:** {p.watch_for}"]
        if a is not None:
            tags = []
            if a.technical:
                tags.append(f"Technical: {a.technical.trend}/{a.technical.stance}")
            if a.fundamental:
                tags.append(f"Định giá: {a.fundamental.valuation}")
            if a.news:
                tags.append(f"Tin tức: {a.news.sentiment}")
            if a.risk:
                tags.append(f"Rủi ro: {a.risk.risk_level}")
            if tags:
                section.append(" · ".join(tags))
            if a.news and a.news.source_urls:
                section.append(
                    "Nguồn: "
                    + ", ".join(f"[{i + 1}]({u})" for i, u in enumerate(a.news.source_urls[:3]))
                )
            if a.errors:
                section.append(f"⚠️ Thiếu phân tích: {'; '.join(a.errors)}")
        out.append("\n\n".join(section))

    if guardrail is not None and not guardrail.ok:
        out.append(
            "> ⚠️ **Guardrail:** các số sau không khớp dữ liệu tool, cần kiểm tra lại: "
            + ", ".join(guardrail.unsupported)
        )
    out.append(DISCLAIMER)
    return "\n\n".join(out) + "\n"
