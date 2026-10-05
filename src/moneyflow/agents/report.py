"""Report agent: chỉ nhận schema có cấu trúc, sinh phần diễn giải cho báo cáo."""

from __future__ import annotations

from typing import Any

import pandas as pd

from moneyflow.llm.client import LLM
from moneyflow.llm.schemas import ReportNarrative, TickerAnalysis

SCORE_COLUMNS = ["rank", "flow_score", "close", "dollar_volume", "rvol", "cmf", "mfi", "rs_short"]


def report_input(top: pd.DataFrame, analyses: list[TickerAnalysis]) -> dict[str, Any]:
    cols = [c for c in SCORE_COLUMNS if c in top.columns]
    ranking = [
        {"ticker": t, **{c: round(float(v), 4) for c, v in row[cols].items()}}
        for t, row in top.iterrows()
    ]
    return {
        "ranking": ranking,
        "analyses": [a.model_dump(exclude={"errors"}) for a in analyses],
    }


def report_agent(
    top: pd.DataFrame, analyses: list[TickerAnalysis], llm: LLM, feedback: str = ""
) -> ReportNarrative:
    instruction = ""
    if feedback:
        instruction = (
            "Bản trước có con số không khớp dữ liệu tool: "
            f"{feedback}. Viết lại, chỉ dùng số liệu có trong dữ liệu."
        )
    return llm.structured(report_input(top, analyses), ReportNarrative, instruction)
