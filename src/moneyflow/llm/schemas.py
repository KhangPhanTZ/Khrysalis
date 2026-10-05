"""Output có cấu trúc của từng agent.

Report agent chỉ nhận các schema này, không nhận text tự do.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Stance = Literal["bullish", "neutral", "bearish"]


class TechnicalView(BaseModel):
    ticker: str
    trend: Literal["uptrend", "sideways", "downtrend"]
    stance: Stance
    confidence: float = Field(ge=0, le=1)
    key_points: list[str] = Field(description="2–4 ý, chỉ dẫn số liệu có trong dữ liệu tool")
    summary: str


class FundamentalView(BaseModel):
    ticker: str
    valuation: Literal["cheap", "fair", "expensive", "unknown"]
    quality: Literal["high", "medium", "low", "unknown"]
    stance: Stance
    key_points: list[str]
    summary: str


class NewsView(BaseModel):
    ticker: str
    sentiment: Literal["positive", "mixed", "negative", "none"]
    catalysts: list[str] = Field(description="Sự kiện có thể giải thích dòng tiền")
    source_urls: list[str] = Field(description="URL lấy nguyên văn từ dữ liệu tin tức")
    summary: str


class RiskView(BaseModel):
    ticker: str
    risk_level: Literal["low", "medium", "high"]
    key_risks: list[str]
    summary: str


class TickerAnalysis(BaseModel):
    ticker: str
    technical: TechnicalView | None = None
    fundamental: FundamentalView | None = None
    news: NewsView | None = None
    risk: RiskView | None = None
    errors: list[str] = Field(default_factory=list)


class ReportPick(BaseModel):
    ticker: str
    stance: Stance
    thesis: str = Field(description="2–3 câu vì sao dòng tiền đổ vào mã này")
    watch_for: str = Field(description="Điều cần theo dõi / điều kiện vô hiệu luận điểm")


class ReportNarrative(BaseModel):
    headline: str
    market_overview: str
    picks: list[ReportPick]
