# moneyflow-agents

Multi-agent system that screens US stocks by money flow and generates daily AI research reports (LangGraph + Claude).

Mỗi sáng hệ thống lọc ra 10–15 mã Mỹ có dòng tiền mạnh nhất (Nasdaq-100 + watchlist, benchmark QQQ) và gửi báo cáo phân tích qua Telegram.

**Nguyên tắc cốt lõi:** mọi con số đều do code tính, LLM chỉ diễn giải và tổng hợp. Một guardrail đối chiếu mọi con số trong báo cáo với output của tool trước khi phát hành.

> Hệ thống chỉ hỗ trợ phân tích, không phải khuyến nghị đầu tư. Không tự động đặt lệnh.

## Kiến trúc

```
data (yfinance, Finnhub, EDGAR + cache DuckDB)
  → analytics (dollar volume, RVOL, CMF, MFI, RS vs QQQ, risk — thuần code, có test)
    → agents: Screener (code) → Technical / Fundamental / News / Risk (LLM, Pydantic output)
      → graph (LangGraph): analyze → report → verify (guardrail số liệu, sinh lại nếu sai) → render
        → reports (Markdown) / apps (Streamlit, Telegram)
```

### Điểm dòng tiền

Mỗi thành phần được xếp hạng percentile trong universe rồi lấy trung bình có trọng số (`config/screener.yaml`):

| Thành phần | Ý nghĩa | Trọng số mặc định |
|---|---|---:|
| Dollar volume 20 phiên | Quy mô tiền giao dịch | 0.15 |
| RVOL (TB 5 phiên) | Volume so với TB 20 phiên trước | 0.25 |
| CMF 20 | Áp lực mua/bán trong range | 0.20 |
| MFI 14 | RSI có trọng số volume | 0.10 |
| RS 20 phiên vs QQQ | Sức mạnh tương đối ngắn hạn | 0.20 |
| RS 60 phiên vs QQQ | Sức mạnh tương đối trung hạn | 0.10 |

Mã có dollar volume trung bình dưới `min_avg_dollar_volume` bị loại.

## Bắt đầu

```bash
uv sync --extra agents            # + --extra apps --extra backtest nếu cần
cp .env.example .env              # điền ANTHROPIC_API_KEY, FINNHUB_KEY, TELEGRAM_TOKEN…

uv run moneyflow fetch QQQ PLTR --days 365   # tải giá vào DuckDB; chạy lại sẽ lấy từ cache
uv run moneyflow screen                      # top 15 kèm điểm, không cần LLM
uv run moneyflow run --telegram              # pipeline đầy đủ + gửi Telegram
```

Dashboard và bot:

```bash
uv sync --extra apps
uv run streamlit run apps/dashboard/app.py
uv run python apps/telegram_bot/bot.py
```

Backtest tín hiệu screener (mua đều top N, giữ 5 phiên, so với QQQ):

```bash
uv sync --extra backtest
uv run python -m backtest.screener_backtest --start 2025-01-01 --end 2026-09-30
```

## LLM

- `get_llm(role)`: model rẻ cho analyst (`MONEYFLOW_MODEL_ANALYST`, mặc định `claude-sonnet-5-5`), model mạnh cho report (`MONEYFLOW_MODEL_REPORT`, mặc định `claude-opus-5-5`).
- Structured output qua `client.messages.parse(output_format=<Pydantic>)`.
- System prompt được prompt-cache; kết quả agent cache theo (role, model, prompt version, dữ liệu) trong `data/llm_cache/`.
- Server-side refusal fallback bật mặc định (`MONEYFLOW_LLM_FALLBACKS=default`, để trống để tắt).
- Chi phí token in ra cuối mỗi lần chạy (`llm/cost.py`).
- Eval: `uv run python -m evals.run_evals` chấm độ chính xác số liệu và độ bám nguồn tin trên golden set.

## Cấu trúc repo

```
config/             universe.yaml, screener.yaml
src/moneyflow/
  data/             DataProvider, yfinance, finnhub, edgar, cache DuckDB
  analytics/        indicators.py, flow_score.py, risk.py
  llm/              client.py, prompts/, schemas.py, guardrail.py, cost.py
  agents/           screener, analysts (technical/fundamental/news/risk), report, tools
  graph/            LangGraph state + workflow
  reports/          template Markdown
  cli.py            moneyflow fetch | screen | run
apps/               dashboard (Streamlit), telegram_bot
backtest/           backtest tín hiệu screener (pandas + vectorbt)
evals/              golden set + chấm điểm
tests/              unit test (không gọi mạng, không gọi LLM)
docker/             Dockerfile
.github/workflows/  ci.yml, daily-report.yml
```

## Lộ trình 8 tuần

| Giai đoạn | Tuần | Nội dung | Trạng thái |
|---|---|---|---|
| 0 · Setup repo | 1 | uv, ruff, mypy, pytest, pre-commit, CI, CLAUDE.md | ✅ |
| 1 · Data layer | 1–2 | DataProvider (yfinance), cache DuckDB, universe.yaml | ✅ |
| 2 · Screener dòng tiền | 2–3 | indicators, flow_score + unit test, `moneyflow screen` | ✅ |
| 3 · Agents + LangGraph | 3–5 | LLM client, tools, 4 analyst, report, guardrail | 🟡 khung đã có, cần chạy thật & tinh chỉnh prompt |
| 4 · Apps + tự động hoá | 6 | Streamlit, Telegram, cron hằng ngày | 🟡 khung đã có |
| 5 · Eval, backtest, hoàn thiện | 7–8 | vectorbt, evals, Langfuse, Docker, demo | 🟡 khung đã có |

## License

MIT
