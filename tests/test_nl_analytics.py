from __future__ import annotations

import unittest

from app.nl_analytics import build_sql, detect_metrics


class NaturalLanguageAnalyticsTests(unittest.TestCase):
    def test_profit_rate_ranking_uses_profit_rate(self) -> None:
        metrics, order_metric, wants_share = detect_metrics("各产品利润率排行")

        self.assertEqual(metrics, ["profit_rate"])
        self.assertEqual(order_metric, "profit_rate")
        self.assertFalse(wants_share)

    def test_share_sql_is_compatible_with_mysql_57(self) -> None:
        where = "WHERE o.ship_time >= %(start_time)s AND o.ship_time < %(end_time_exclusive)s"
        plan = build_sql(
            "各产品销售额占比",
            where,
            {"start_time": "2026-01-01", "end_time_exclusive": "2027-01-01"},
        )

        self.assertNotIn(" OVER ", plan["sql"])
        self.assertIn("CROSS JOIN", plan["sql"])
        self.assertIn("MAX(share_totals.total_revenue)", plan["sql"])
        self.assertEqual(plan["sql"].count(where), 2)

    def test_non_share_sql_skips_total_subquery(self) -> None:
        where = "WHERE o.ship_time >= %(start_time)s AND o.ship_time < %(end_time_exclusive)s"
        plan = build_sql(
            "各产品销售额排行",
            where,
            {"start_time": "2026-01-01", "end_time_exclusive": "2027-01-01"},
        )

        self.assertNotIn("CROSS JOIN", plan["sql"])
        self.assertNotIn("share_totals", plan["sql"])


if __name__ == "__main__":
    unittest.main()
