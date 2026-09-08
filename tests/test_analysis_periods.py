from __future__ import annotations

import unittest

from app.analysis_periods import comparison_period


class AnalysisPeriodTests(unittest.TestCase):
    def test_complete_single_month_uses_previous_calendar_month(self) -> None:
        result = comparison_period(
            {"start_time": "2026-03-01", "end_time": "2026-03-31"}
        )

        self.assertEqual(
            result,
            {
                "start_time": "2026-02-01",
                "end_time": "2026-02-28",
                "mode": "previous_period",
                "label": "上一个自然月",
            },
        )

    def test_complete_multi_month_period_uses_previous_calendar_months(self) -> None:
        result = comparison_period(
            {"start_time": "2026-01-01", "end_time": "2026-03-31"}
        )

        self.assertEqual(result["start_time"], "2025-10-01")
        self.assertEqual(result["end_time"], "2025-12-31")
        self.assertEqual(result["mode"], "previous_period")
        self.assertEqual(result["label"], "前 3 个自然月")

    def test_partial_period_uses_immediately_preceding_equal_day_count(self) -> None:
        result = comparison_period(
            {"start_time": "2026-03-05", "end_time": "2026-03-20"}
        )

        self.assertEqual(result["start_time"], "2026-02-17")
        self.assertEqual(result["end_time"], "2026-03-04")
        self.assertEqual(result["label"], "前一等长周期")

    def test_year_over_year_uses_calendar_dates_and_clamps_leap_day(self) -> None:
        result = comparison_period(
            {
                "start_time": "2024-02-29",
                "end_time": "2024-02-29",
                "comparison_mode": "year_over_year",
            }
        )

        self.assertEqual(
            result,
            {
                "start_time": "2023-02-28",
                "end_time": "2023-02-28",
                "mode": "year_over_year",
                "label": "去年同期",
            },
        )

    def test_invalid_period_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "结束日期不能早于开始日期"):
            comparison_period(
                {"start_time": "2026-03-02", "end_time": "2026-03-01"}
            )


if __name__ == "__main__":
    unittest.main()
