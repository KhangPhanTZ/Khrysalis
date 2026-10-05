"""Gửi báo cáo qua Telegram Bot API (dùng HTTP thuần để chạy được trong cron)."""

from __future__ import annotations

import requests

from moneyflow.config import Settings

TELEGRAM_LIMIT = 4000  # giới hạn 4096 ký tự/tin, chừa biên


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Cắt theo đoạn để không vỡ bảng/đoạn văn giữa chừng."""
    chunks: list[str] = []
    buf = ""
    for para in text.split("\n\n"):
        while len(para) > limit:  # đoạn quá dài: cắt cứng
            chunks.append(para[:limit])
            para = para[limit:]
        candidate = f"{buf}\n\n{para}" if buf else para
        if len(candidate) > limit:
            chunks.append(buf)
            buf = para
        else:
            buf = candidate
    if buf:
        chunks.append(buf)
    return chunks


def send_telegram(text: str, settings: Settings) -> None:
    if not settings.telegram_token or not settings.telegram_chat_id:
        raise RuntimeError("Thiếu TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    for chunk in split_message(text):
        resp = requests.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        resp.raise_for_status()
