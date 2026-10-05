"""Client LLM duy nhất. `get_llm(role)` trả về model theo vai trò — cấu hình trong .env."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from moneyflow.config import Settings, get_settings
from moneyflow.llm.cost import CostTracker
from moneyflow.llm.prompt_loader import system_prompt

log = logging.getLogger(__name__)

Role = Literal["technical", "fundamental", "news", "risk", "report"]
T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMRefusalError(RuntimeError):
    """Model từ chối trả lời (stop_reason = refusal) sau cả chuỗi fallback."""


class LLM:
    """Bọc Anthropic SDK: system prompt được cache, output là Pydantic schema."""

    def __init__(
        self,
        role: Role,
        model: str,
        settings: Settings,
        tracker: CostTracker | None = None,
        client: Any | None = None,
        max_tokens: int = 16000,
        cache_dir: Path | None = None,
    ) -> None:
        self.role = role
        self.model = model
        self.settings = settings
        self.tracker = tracker or CostTracker()
        self.max_tokens = max_tokens
        self.cache_dir = cache_dir
        self.system, self.prompt_version = system_prompt(role)
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
        self._client = client

    def structured(self, data: dict[str, Any], schema: type[T], instruction: str = "") -> T:
        """Gửi DỮ LIỆU TOOL (JSON) và nhận về instance của `schema`."""
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        content = f"DỮ LIỆU TOOL:\n```json\n{payload}\n```"
        if instruction:
            content += f"\n\n{instruction}"

        cache_file = self._cache_file(content, schema)
        if cache_file is not None and cache_file.exists():
            return schema.model_validate_json(cache_file.read_text(encoding="utf-8"))

        extra: dict[str, Any] = {}
        if self.settings.moneyflow_llm_fallbacks:
            extra["extra_headers"] = {"anthropic-beta": FALLBACK_BETA}
            extra["extra_body"] = {"fallbacks": self.settings.moneyflow_llm_fallbacks}

        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            # System prompt cố định -> cache prefix giữa các mã trong cùng một lần chạy
            system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            metadata={"user_id": f"moneyflow-{self.role}"},
            **extra,
        )
        self._record_usage(response)

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusalError(f"{self.role}: model từ chối ({details})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{self.role}: output bị cắt do max_tokens")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError(f"{self.role}: không parse được output")
        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")
        return parsed  # type: ignore[no-any-return]

    def _cache_file(self, content: str, schema: type[BaseModel]) -> Path | None:
        """Cache theo (role, model, prompt version, schema, dữ liệu). Dữ liệu chứa ticker + ngày."""
        if self.cache_dir is None:
            return None
        key = f"{self.model}|{self.prompt_version}|{schema.__name__}|{content}"
        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / self.role / f"{digest}.json"

    def _record_usage(self, response: Any) -> None:
        u = getattr(response, "usage", None)
        if u is None:
            return
        self.tracker.record(
            getattr(response, "model", self.model),
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        )


def get_llm(
    role: Role,
    settings: Settings | None = None,
    tracker: CostTracker | None = None,
    client: Any | None = None,
    cache_dir: Path | None = None,
) -> LLM:
    """Model rẻ cho analyst (technical/fundamental/news/risk), model mạnh cho report."""
    s = settings or get_settings()
    model = s.moneyflow_model_report if role == "report" else s.moneyflow_model_analyst
    return LLM(role, model, s, tracker=tracker, client=client, cache_dir=cache_dir)
