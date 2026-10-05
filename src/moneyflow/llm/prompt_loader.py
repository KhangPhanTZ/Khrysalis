"""Nạp prompt từ llm/prompts/*.md."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
_VERSION_RE = re.compile(r"<!--\s*version:\s*(\S+)\s*-->")


@lru_cache
def load_prompt(name: str) -> tuple[str, str]:
    """Trả về (nội dung, version). Nội dung đã bỏ dòng version."""
    text = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = _VERSION_RE.search(text)
    version = m.group(1) if m else "0"
    return _VERSION_RE.sub("", text, count=1).strip(), version


def system_prompt(role: str) -> tuple[str, str]:
    """Prompt chung + prompt của vai trò. Version dạng `shared.role`."""
    shared, v_shared = load_prompt("_shared")
    body, v_role = load_prompt(role)
    return f"{shared}\n\n{body}", f"{v_shared}.{v_role}"
