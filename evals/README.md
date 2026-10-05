# Evals

Bộ golden set để chấm báo cáo AI theo hai tiêu chí:

1. **Độ chính xác số liệu** — mọi con số trong phần LLM viết phải khớp output tool
   (`moneyflow.llm.guardrail.check_numbers`).
2. **Độ bám nguồn tin** — mọi URL trong `NewsView.source_urls` phải nằm trong dữ liệu tin tức đã đưa vào.

`golden.yaml` chứa 20–30 cặp (ngày, mã). Chạy:

```bash
uv run --extra agents python -m evals.run_evals
```

Kết quả ghi ra `evals/results/<timestamp>.json`; theo dõi xu hướng qua các version prompt.
