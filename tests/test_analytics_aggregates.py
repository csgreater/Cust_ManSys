from __future__ import annotations

import unittest

from app.analytics_aggregates import (
    can_use_global_monthly,
    can_use_product_monthly,
    product_monthly_where,
)


ADMIN_USER = {
    "all_scopes": {"dept": True, "platform": True, "shop": True},
    "scopes": {"dept": [], "platform": [], "shop": []},
}


class AnalyticsAggregateTests(unittest.TestCase):
    def test_only_complete_calendar_months_use_aggregate(self) -> None:
        self.assertTrue(
            can_use_product_monthly(
                {"start_time": "2026-05-01", "end_time": "2026-06-30", "order_no": ""}
            )
        )
        self.assertFalse(
            can_use_product_monthly(
                {"start_time": "2026-05-02", "end_time": "2026-06-30", "order_no": ""}
            )
        )
        self.assertFalse(
            can_use_product_monthly(
                {"start_time": "2026-05-01", "end_time": "2026-06-30", "order_no": "A"}
            )
        )

    def test_reversed_complete_month_range_does_not_use_aggregate(self) -> None:
        filters = {"start_time": "2026-06-01", "end_time": "2026-05-31"}

        self.assertFalse(can_use_product_monthly(filters))
        self.assertFalse(can_use_global_monthly(ADMIN_USER, filters))

    def test_product_aggregate_falls_back_for_unsupported_detail_filters(self) -> None:
        base_filters = {
            "start_time": "2026-06-01",
            "end_time": "2026-06-30",
            "order_no": "",
        }

        for field, value in (
            ("province", "上海"),
            ("city", "上海市"),
            ("order_source", "直播"),
            ("product", "SKU-ONLY-001"),
        ):
            with self.subTest(field=field):
                filters = {**base_filters, field: value}
                self.assertFalse(can_use_product_monthly(filters))

    def test_monthly_where_preserves_business_filters(self) -> None:
        filters = {
            "start_time": "2026-06-01",
            "end_time": "2026-06-30",
            "dept": "D1",
            "platform": "P1",
            "shop_name": "S1",
            "category": "C1",
            "product_classification": "PC1",
            "product": "",
            "order_no": "",
        }

        where, params = product_monthly_where(ADMIN_USER, filters)

        self.assertIn("a.stat_month >= %(start_month)s", where)
        self.assertIn("a.dept = %(dept)s", where)
        self.assertEqual(params["start_month"], "2026-06-01")
        self.assertEqual(params["end_month"], "2026-06-01")

    def test_global_monthly_requires_admin_scope_and_no_filters(self) -> None:
        filters = {
            "start_time": "2026-06-01",
            "end_time": "2026-06-30",
            "dept": "",
            "platform": "",
            "shop_name": "",
            "category": "",
            "product_classification": "",
            "product": "",
            "order_no": "",
        }
        self.assertTrue(can_use_global_monthly(ADMIN_USER, filters))
        filters["dept"] = "D1"
        self.assertFalse(can_use_global_monthly(ADMIN_USER, filters))

    def test_global_aggregate_falls_back_for_region_and_source_filters(self) -> None:
        base_filters = {
            "start_time": "2026-06-01",
            "end_time": "2026-06-30",
        }

        for field, value in (
            ("province", "上海"),
            ("city", "上海市"),
            ("order_source", "直播"),
        ):
            with self.subTest(field=field):
                self.assertFalse(can_use_global_monthly(ADMIN_USER, {**base_filters, field: value}))


if __name__ == "__main__":
    unittest.main()
