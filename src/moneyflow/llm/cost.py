"""Theo dõi token và chi phí LLM theo model."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# USD / 1M token: (input, output, cache read). Cập nhật khi bảng giá thay đổi.
PRICING: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    calls: int = 0


@dataclass
class CostTracker:
    by_model: dict[str, Usage] = field(default_factory=lambda: defaultdict(Usage))

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        u = self.by_model[model]
        u.input_tokens += input_tokens
        u.output_tokens += output_tokens
        u.cache_read_tokens += cache_read_tokens
        u.cache_write_tokens += cache_write_tokens
        u.calls += 1

    def cost_usd(self) -> float:
        total = 0.0
        for model, u in self.by_model.items():
            p_in, p_out, p_cache = PRICING.get(model, (0.0, 0.0, 0.0))
            # cache write tính 1.25x giá input (TTL 5 phút)
            total += (
                u.input_tokens * p_in
                + u.output_tokens * p_out
                + u.cache_read_tokens * p_cache
                + u.cache_write_tokens * p_in * 1.25
            ) / 1_000_000
        return round(total, 4)

    def summary(self) -> str:
        parts = [
            f"{m}: {u.calls} calls, in={u.input_tokens} out={u.output_tokens} "
            f"cache_read={u.cache_read_tokens}"
            for m, u in self.by_model.items()
        ]
        return "; ".join(parts) + f" | ≈ ${self.cost_usd():.4f}"
