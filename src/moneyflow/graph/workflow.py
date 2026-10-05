"""LangGraph workflow: analyze -> report -> verify (-> report lần nữa nếu sai số liệu)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from moneyflow.agents.analysts import fundamental_agent, news_agent, risk_agent, technical_agent
from moneyflow.agents.report import report_agent, report_input
from moneyflow.agents.screener import ScreenResult
from moneyflow.agents.tools import Toolbox
from moneyflow.graph.state import RunState
from moneyflow.llm.client import LLM
from moneyflow.llm.guardrail import check_numbers
from moneyflow.llm.schemas import TickerAnalysis
from moneyflow.reports.markdown import narrative_text, render_report

log = logging.getLogger(__name__)

MAX_REPORT_ATTEMPTS = 3


@dataclass
class Agents:
    technical: LLM
    fundamental: LLM
    news: LLM
    risk: LLM
    report: LLM
    max_workers: int = 4
    extra: dict[str, Any] = field(default_factory=dict)


def analyze_ticker(ticker: str, tools: Toolbox, agents: Agents) -> TickerAnalysis:
    result = TickerAnalysis(ticker=ticker)
    # news trước risk: risk agent dùng lại headline trong ledger
    steps: list[tuple[str, Callable[[], BaseModel]]] = [
        ("technical", lambda: technical_agent(ticker, tools, agents.technical)),
        ("fundamental", lambda: fundamental_agent(ticker, tools, agents.fundamental)),
        ("news", lambda: news_agent(ticker, tools, agents.news)),
        ("risk", lambda: risk_agent(ticker, tools, agents.risk)),
    ]
    for name, fn in steps:
        try:
            setattr(result, name, fn())
        except Exception as e:  # một agent lỗi không làm hỏng cả báo cáo
            log.exception("%s agent lỗi cho %s", name, ticker)
            result.errors.append(f"{name}: {e}")
    return result


def build_graph(screen: ScreenResult, tools: Toolbox, agents: Agents) -> Any:
    from langgraph.graph import END, START, StateGraph

    def analyze(state: RunState) -> RunState:
        tickers = state["tickers"]
        with ThreadPoolExecutor(max_workers=agents.max_workers) as pool:
            analyses = list(pool.map(lambda t: analyze_ticker(t, tools, agents), tickers))
        return {"analyses": analyses}

    def report(state: RunState) -> RunState:
        narrative = report_agent(
            screen.top, state["analyses"], agents.report, feedback=state.get("feedback", "")
        )
        return {"narrative": narrative, "attempts": state.get("attempts", 0) + 1}

    def verify(state: RunState) -> RunState:
        narrative = state["narrative"]
        assert narrative is not None
        sources = [tools.ledger, report_input(screen.top, state["analyses"])]
        result = check_numbers(narrative_text(narrative), sources)
        if not result.ok:
            log.warning("Guardrail: số liệu không khớp %s", result.unsupported)
        return {"guardrail": result, "feedback": ", ".join(result.unsupported)}

    def route(state: RunState) -> str:
        g = state["guardrail"]
        if g is not None and not g.ok and state.get("attempts", 0) < MAX_REPORT_ATTEMPTS:
            return "report"
        return "render"

    def render(state: RunState) -> RunState:
        md = render_report(
            as_of=state["as_of"],
            top=screen.top,
            universe_size=len(screen.scores),
            analyses=state["analyses"],
            narrative=state["narrative"],
            guardrail=state["guardrail"],
        )
        return {"report_markdown": md}

    g = StateGraph(RunState)
    g.add_node("analyze", analyze)
    g.add_node("report", report)
    g.add_node("verify", verify)
    g.add_node("render", render)
    g.add_edge(START, "analyze")
    g.add_edge("analyze", "report")
    g.add_edge("report", "verify")
    g.add_conditional_edges("verify", route, {"report": "report", "render": "render"})
    g.add_edge("render", END)
    return g.compile()


def run_pipeline(screen: ScreenResult, tools: Toolbox, agents: Agents) -> RunState:
    graph = build_graph(screen, tools, agents)
    init: RunState = {"as_of": screen.as_of, "tickers": list(screen.top.index), "attempts": 0}
    out: RunState = graph.invoke(init)
    return out
