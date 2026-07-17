from __future__ import annotations

import unittest

from app.nl_analytics import build_sql, detect_metrics


class NaturalLanguageAnalyticsTests(unittest.TestCase):
    def test_profit_rate_ranking_uses_profit_rate(self) -> None:
        metrics, order_metric, wants_share = detect_metrics("各产品利润率排行")

        self.assertEqual(metrics, ["profit_rate"])
        self.assertEqual(order_metric, "profit_rate")
        self.assertFalse(wants_share)

    def test_share_sql_uses_single_scan_window_aggregate(self) -> None:
        where = "WHERE o.ship_time >= %(start_time)s AND o.ship_time < %(end_time_exclusive)s"
        plan = build_sql(
            "各产品销售额占比",
            where,
            {"start_time": "2026-01-01", "end_time_exclusive": "2027-01-01"},
        )

        self.assertIn("SUM(SUM(o.share_receivable)) OVER ()", plan["sql"])
        self.assertNotIn("CROSS JOIN", plan["sql"])


if __name__ == "__main__":
    unittest.main()
