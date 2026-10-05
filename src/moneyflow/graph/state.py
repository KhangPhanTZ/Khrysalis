"""State của LangGraph workflow."""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from moneyflow.llm.guardrail import GuardrailResult
from moneyflow.llm.schemas import ReportNarrative, TickerAnalysis


class RunState(TypedDict, total=False):
    as_of: date
    tickers: list[str]
    analyses: list[TickerAnalysis]
    narrative: ReportNarrative | None
    guardrail: GuardrailResult | None
    attempts: int
    feedback: str
    report_markdown: str
    meta: dict[str, Any]
