FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra agents --extra apps --no-install-project

COPY config ./config
COPY src ./src
COPY apps ./apps
RUN uv sync --frozen --no-dev --extra agents --extra apps

ENV PATH="/app/.venv/bin:$PATH"
# Mặc định: chạy pipeline hằng ngày và gửi Telegram. Ghi đè CMD để chạy dashboard:
#   docker run -p 8501:8501 IMAGE streamlit run apps/dashboard/app.py --server.address 0.0.0.0
CMD ["moneyflow", "run", "--date", "today", "--telegram"]
