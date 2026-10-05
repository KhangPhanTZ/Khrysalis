from __future__ import annotations

from moneyflow.llm.guardrail import check_numbers, extract_numbers


def test_extract_numbers() -> None:
    nums = [v for _, v, _ in extract_numbers("RVOL 2.35, giá $1,234.5, giảm -3.2%, Q3 10-K")]
    assert nums == [2.35, 1234.5, -3.2]


def test_supported_numbers_pass() -> None:
    tools = {"indicators": {"rsi_14": 71.234, "close": 182.5}, "flow": {"rs_short": 0.0812}}
    text = "RSI 71.2, giá đóng cửa 182.50, mạnh hơn QQQ 8.1% trong 5 phiên năm 2026."
    res = check_numbers(text, [tools])
    assert res.ok, res.unsupported
    assert res.checked == 3  # bỏ qua số nguyên nhỏ (5) và năm (2026)


def test_hallucinated_number_flagged() -> None:
    tools = {"indicators": {"rsi_14": 55.0}}
    res = check_numbers("RSI 55, mục tiêu giá 250.75", [tools])
    assert not res.ok
    assert res.unsupported == ["250.75"]


def test_numbers_inside_tool_strings_allowed() -> None:
    news = [{"headline": "Company raises guidance to $4.2B revenue"}]
    assert check_numbers("Nâng dự báo doanh thu lên 4.2 tỉ USD", [news]).ok
