"""Guardrail số liệu: mọi con số trong văn bản LLM phải khớp với output của tool."""

from __future__ import annotations

import bisect
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

# Số có thể kèm dấu, phân cách nghìn, thập phân, hậu tố K/M/B/T ("$4.2B");
# không dính liền chữ cái (bỏ "Q3", "10-K", "S&P500")
_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-])[-+−]?\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
    r"(?:[KMBT](?![A-Za-z]))?(?![A-Za-z0-9_]|-[A-Za-z])"
)


@dataclass
class GuardrailResult:
    ok: bool
    checked: int
    unsupported: list[str] = field(default_factory=list)


def extract_numbers(text: str) -> list[tuple[str, float, int]]:
    """Trả về (chuỗi gốc, giá trị, số chữ số thập phân)."""
    out: list[tuple[str, float, int]] = []
    for m in _NUM_RE.finditer(text):
        raw = m.group(0)
        intpart, frac = m.group(1), m.group(2) or ""
        value = float(intpart.replace(",", "") + frac)
        if raw.lstrip("$").startswith(("-", "−")):
            value = -value
        out.append((raw, value, max(len(frac) - 1, 0)))
    return out


def _walk(obj: Any) -> Iterator[float]:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        if not math.isnan(obj) and not math.isinf(obj):
            yield float(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            yield from _walk(v)
    elif isinstance(obj, str):
        for _, v, _ in extract_numbers(obj):
            yield v


def allowed_values(sources: Iterable[Any]) -> list[float]:
    """Tập giá trị hợp lệ (trị tuyệt đối): mọi số trong output tool, kèm dạng % (x100),
    dạng tỉ lệ (/100) và dạng rút gọn triệu/tỉ (/1e6, /1e9)."""
    vals: set[float] = set()
    for src in sources:
        for v in _walk(src):
            a = abs(v)
            vals.update({a, a * 100, a / 100, a / 1e6, a / 1e9})
    return sorted(vals)


def _matches(value: float, decimals: int, allowed: list[float]) -> bool:
    # Cho phép LLM làm tròn bớt: sai lệch tối đa nửa đơn vị ở chữ số thập phân cuối cùng
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    target = abs(value)
    i = bisect.bisect_left(allowed, target - tol)
    return i < len(allowed) and allowed[i] <= target + tol


def check_numbers(
    text: str,
    sources: Iterable[Any],
    ignore_small_ints: int = 10,
    extra_allowed: Iterable[float] = (),
) -> GuardrailResult:
    """Kiểm tra mọi con số trong `text` có nguồn trong `sources`.

    Bỏ qua số nguyên nhỏ (≤ `ignore_small_ints`, ví dụ "top 3", "2 phiên") và năm (1900–2100).
    """
    allowed = sorted([*allowed_values(sources), *(abs(v) for v in extra_allowed)])
    unsupported: list[str] = []
    checked = 0
    for raw, value, decimals in extract_numbers(text):
        is_int = decimals == 0 and "." not in raw
        if is_int and abs(value) <= ignore_small_ints:
            continue
        if is_int and 1900 <= value <= 2100:
            continue
        checked += 1
        if not _matches(value, decimals, allowed):
            unsupported.append(raw)
    return GuardrailResult(ok=not unsupported, checked=checked, unsupported=unsupported)
