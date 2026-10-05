"""Cấu hình: biến môi trường (.env) và file YAML trong config/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    """Bí mật và tuỳ chọn runtime, đọc từ biến môi trường hoặc .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    moneyflow_model_analyst: str = "claude-sonnet-5-5"
    moneyflow_model_report: str = "claude-opus-5-5"
    moneyflow_llm_fallbacks: str = "default"

    finnhub_key: str = ""
    sec_user_agent: str = "moneyflow-agents contact@example.com"
    moneyflow_db_path: Path = PROJECT_ROOT / "data" / "moneyflow.duckdb"

    telegram_token: str = ""
    telegram_chat_id: str = ""


class Universe(BaseModel):
    benchmark: str = "QQQ"
    nasdaq100: list[str] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)

    @property
    def tickers(self) -> list[str]:
        """Nasdaq-100 + watchlist, bỏ trùng, giữ thứ tự, không gồm benchmark."""
        seen: dict[str, None] = {}
        for t in [*self.nasdaq100, *self.watchlist]:
            t = t.upper().strip()
            if t and t != self.benchmark:
                seen.setdefault(t, None)
        return list(seen)


class ScreenerWindows(BaseModel):
    avg_volume: int = 20
    rvol_smooth: int = 5
    cmf: int = 20
    mfi: int = 14
    rs_short: int = 20
    rs_long: int = 60


class ScreenerConfig(BaseModel):
    lookback_days: int = 260
    min_avg_dollar_volume: float = 50_000_000
    top_n: int = 15
    windows: ScreenerWindows = Field(default_factory=ScreenerWindows)
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "dollar_volume": 0.15,
            "rvol": 0.25,
            "cmf": 0.20,
            "mfi": 0.10,
            "rs_short": 0.20,
            "rs_long": 0.10,
        }
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} phải là mapping YAML")
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_universe(path: Path | None = None) -> Universe:
    return Universe.model_validate(_load_yaml(path or CONFIG_DIR / "universe.yaml"))


def load_screener_config(path: Path | None = None) -> ScreenerConfig:
    return ScreenerConfig.model_validate(_load_yaml(path or CONFIG_DIR / "screener.yaml"))
