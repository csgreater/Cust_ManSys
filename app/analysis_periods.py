from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any


COMPARISON_MODES = {"previous_period", "year_over_year"}


def _parse_date(filters: dict[str, Any], field: str) -> date:
    try:
        return date.fromisoformat(str(filters[field]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{field}必须是 YYYY-MM-DD 日期") from exc


def _shift_month_start(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _shift_year(value: date, years: int) -> date:
    target_year = value.year + years
    target_day = min(value.day, monthrange(target_year, value.month)[1])
    return date(target_year, value.month, target_day)


def _is_complete_calendar_month_range(start: date, end: date) -> bool:
    return start.day == 1 and end.day == monthrange(end.year, end.month)[1]


def comparison_period(filters: dict[str, Any]) -> dict[str, str]:
    """Return the explicit comparison range for an inclusive current period."""

    start = _parse_date(filters, "start_time")
    end = _parse_date(filters, "end_time")
    if end < start:
        raise ValueError("结束日期不能早于开始日期")

    mode = str(filters.get("comparison_mode") or "previous_period")
    if mode not in COMPARISON_MODES:
        raise ValueError("comparison_mode必须是 previous_period 或 year_over_year")

    if mode == "year_over_year":
        compare_start = _shift_year(start, -1)
        compare_end = _shift_year(end, -1)
        label = "去年同期"
    elif _is_complete_calendar_month_range(start, end):
        month_count = (end.year - start.year) * 12 + end.month - start.month + 1
        compare_start = _shift_month_start(start, -month_count)
        compare_end_month = _shift_month_start(start, -1)
        compare_end = compare_end_month.replace(
            day=monthrange(compare_end_month.year, compare_end_month.month)[1]
        )
        label = "上一个自然月" if month_count == 1 else f"前 {month_count} 个自然月"
    else:
        day_count = (end - start).days + 1
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - timedelta(days=day_count - 1)
        label = "前一等长周期"

    return {
        "start_time": compare_start.isoformat(),
        "end_time": compare_end.isoformat(),
        "mode": mode,
        "label": label,
    }
