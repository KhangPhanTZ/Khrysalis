from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from moneyflow.config import Settings
from moneyflow.llm.client import LLMRefusalError, get_llm
from moneyflow.llm.cost import CostTracker
from moneyflow.llm.prompt_loader import system_prompt
from moneyflow.llm.schemas import RiskView


class FakeMessages:
    def __init__(self, stop_reason: str = "end_turn") -> None:
        self.calls: list[dict[str, Any]] = []
        self.stop_reason = stop_reason

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        view = RiskView(ticker="PLTR", risk_level="high", key_risks=["beta cao"], summary="ok")
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            parsed_output=view,
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=200,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


def _settings() -> Settings:
    return Settings(anthropic_api_key="test", moneyflow_model_analyst="claude-sonnet-5-5")


def test_role_routing() -> None:
    fake = SimpleNamespace(messages=FakeMessages())
    assert get_llm("news", _settings(), client=fake).model == "claude-sonnet-5-5"
    assert get_llm("report", _settings(), client=fake).model == "claude-opus-5-5"


def test_structured_call_and_cost(tmp_path: Path) -> None:
    msgs = FakeMessages()
    tracker = CostTracker()
    llm = get_llm(
        "risk", _settings(), tracker, client=SimpleNamespace(messages=msgs), cache_dir=tmp_path
    )
    out = llm.structured({"ticker": "PLTR", "risk": {"beta_120d": 2.1}}, RiskView)
    assert out.risk_level == "high"

    call = msgs.calls[0]
    assert call["output_format"] is RiskView
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert '"beta_120d": 2.1' in call["messages"][0]["content"]
    assert tracker.cost_usd() == pytest.approx((1000 * 2 + 200 * 10) / 1e6)

    # gọi lại cùng dữ liệu -> lấy từ cache, không gọi API
    llm.structured({"ticker": "PLTR", "risk": {"beta_120d": 2.1}}, RiskView)
    assert len(msgs.calls) == 1


def test_refusal_raises() -> None:
    llm = get_llm("risk", _settings(), client=SimpleNamespace(messages=FakeMessages("refusal")))
    with pytest.raises(LLMRefusalError):
        llm.structured({"ticker": "X"}, RiskView)


def test_prompts_have_versions() -> None:
    for role in ("technical", "fundamental", "news", "risk", "report"):
        text, version = system_prompt(role)
        assert "DỮ LIỆU TOOL" in text
        assert version == "1.1"
