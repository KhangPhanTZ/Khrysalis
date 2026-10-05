# CLAUDE.md — moneyflow-agents

## Mục đích
Multi-agent screen cổ phiếu Mỹ theo dòng tiền, sinh báo cáo hằng ngày. Không đặt lệnh.

## Lệnh
- Cài: `uv sync --extra agents` (thêm `--extra apps`, `--extra backtest` khi cần)
- Test: `uv run pytest -q`
- Lint: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- Screener (không cần LLM): `uv run moneyflow screen --date today`
- Chạy đầy đủ: `uv run moneyflow run --date today`

## Quy ước
- Mọi con số tính trong `analytics/`; agent KHÔNG tự tính toán.
- `analytics/` thuần Python, không gọi mạng, bắt buộc có unit test.
- Agent chỉ lấy số liệu qua `agents/tools.py` (`Toolbox`); mọi output tool vào `ledger` để guardrail đối chiếu.
- Output agent = Pydantic schema trong `llm/schemas.py`. Report agent chỉ nhận schema.
- Prompt nằm trong `llm/prompts/*.md` (dòng đầu `<!-- version: N -->`), không viết inline. Đổi nội dung thì tăng version.
- Model chọn theo vai trò qua `get_llm(role)`, cấu hình trong `.env` — không hard-code model trong agent.
- Nguồn dữ liệu mới implement `DataProvider` (`data/base.py`), không gọi thẳng từ agent.
- Không commit `.env` hoặc data cache (`data/`, `*.duckdb`, `reports_out/`).

## Kiến trúc
data → analytics → agents (tools) → graph (LangGraph) → reports/apps
