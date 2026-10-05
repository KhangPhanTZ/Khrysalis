"""Bot Telegram: /report (báo cáo mới nhất), /top (xếp hạng mới nhất).

Chạy: `uv run --extra apps python apps/telegram_bot/bot.py`
Báo cáo hằng ngày được gửi bởi `moneyflow run --telegram` (cron); bot này để tra cứu theo yêu cầu.
"""

from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from moneyflow.config import get_settings
from moneyflow.data.cache import PriceCache
from moneyflow.notify import split_message

REPORT_DIR = Path("reports_out")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    files = sorted(REPORT_DIR.glob("*.md"))
    if not files or update.message is None:
        return
    for chunk in split_message(files[-1].read_text(encoding="utf-8")):
        await update.message.reply_text(chunk, disable_web_page_preview=True)


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    signals = PriceCache(get_settings().moneyflow_db_path).read_signals()
    if signals.empty:
        await update.message.reply_text("Chưa có tín hiệu.")
        return
    last = signals[signals["run_date"] == signals["run_date"].max()].head(15)
    lines = [f"{int(r.rank):>2}. {r.ticker:<6} {r.flow_score:5.1f}" for r in last.itertuples()]
    await update.message.reply_text("Top dòng tiền:\n" + "\n".join(lines))


def main() -> None:
    app = Application.builder().token(get_settings().telegram_token).build()
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("top", top))
    app.run_polling()


if __name__ == "__main__":
    main()
