"""Bốn analyst agent. Mỗi agent: gọi tool lấy số liệu -> LLM diễn giải -> Pydantic schema."""

from __future__ import annotations

from moneyflow.agents.tools import Toolbox
from moneyflow.llm.client import LLM
from moneyflow.llm.schemas import FundamentalView, NewsView, RiskView, TechnicalView


def technical_agent(ticker: str, tools: Toolbox, llm: LLM) -> TechnicalView:
    data = {
        "ticker": ticker,
        "as_of": tools.as_of.isoformat(),
        "indicators": tools.get_indicators(ticker),
        "flow_score": tools.get_flow_score(ticker),
    }
    return llm.structured(data, TechnicalView)


def fundamental_agent(ticker: str, tools: Toolbox, llm: LLM) -> FundamentalView:
    data = {"ticker": ticker, "fundamentals": tools.get_fundamentals(ticker)}
    return llm.structured(data, FundamentalView)


def news_agent(ticker: str, tools: Toolbox, llm: LLM, days: int = 7) -> NewsView:
    data = {
        "ticker": ticker,
        "as_of": tools.as_of.isoformat(),
        "news": tools.get_news(ticker, days),
    }
    return llm.structured(data, NewsView)


def risk_agent(ticker: str, tools: Toolbox, llm: LLM) -> RiskView:
    data = {
        "ticker": ticker,
        "risk": tools.get_risk(ticker),
        # dùng lại kết quả đã có trong ledger nếu agent khác đã gọi, tránh gọi mạng lần nữa
        "news_headlines": [n["headline"] for n in tools.ledger.get(ticker, {}).get("news", [])][
            :10
        ],
    }
    return llm.structured(data, RiskView)
