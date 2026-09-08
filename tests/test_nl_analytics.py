from __future__ import annotations

import unittest
from datetime import date

from app.nl_analytics import (
    build_rule_intent,
    build_sql,
    collapse_filtered_dimensions,
    detect_metrics,
    normalize_analysis_intent_v2,
    resolve_filter_entities,
)


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

    def test_compound_question_extracts_time_metrics_and_filter_hints(self) -> None:
        intent = build_rule_intent(
            "看抖音平台华东区域女装今年上半年的销售额、利润率和月度趋势",
            today=date(2026, 7, 24),
        )

        self.assertEqual(intent["analysis_type"], "trend")
        self.assertEqual(intent["time_range"]["start_time"], "2026-01-01")
        self.assertEqual(intent["time_range"]["end_time"], "2026-06-30")
        self.assertEqual(intent["filter_hints"]["platform"], "抖音")
        self.assertEqual(intent["filter_hints"]["dept"], "华东")
        self.assertEqual(intent["dimensions"], ["month", "platform"])
        self.assertEqual(intent["metrics"], ["revenue", "profit_rate"])

    def test_year_over_year_keeps_current_period_as_primary(self) -> None:
        intent = build_rule_intent("今年各店铺比去年同期销售额增长多少", today=date(2026, 7, 24))

        self.assertEqual(intent["time_range"]["start_time"], "2026-01-01")
        self.assertEqual(intent["time_range"]["end_time"], "2026-07-24")
        self.assertEqual(intent["comparison"]["mode"], "year_over_year")
        self.assertEqual(intent["comparison"]["start_time"], "2025-01-01")
        self.assertEqual(intent["comparison"]["end_time"], "2025-07-24")

    def test_entity_resolution_uses_permission_scoped_catalog_values(self) -> None:
        intent = build_rule_intent(
            "看抖音平台华东区域女装今年上半年的销售额和月度趋势",
            today=date(2026, 7, 24),
        )
        resolved, clarifications = resolve_filter_entities(
            "看抖音平台华东区域女装今年上半年的销售额和月度趋势",
            intent,
            {
                "platform": ["抖音", "天猫"],
                "dept": ["华东", "华南"],
                "category": ["女装", "男装"],
            },
        )
        intent["filters"].update(resolved)

        self.assertFalse(clarifications)
        self.assertEqual(resolved["platform"], "抖音")
        self.assertEqual(resolved["dept"], "华东")
        self.assertEqual(resolved["category"], "女装")
        self.assertEqual(collapse_filtered_dimensions("看抖音平台按月趋势", intent), ["month"])

    def test_entity_resolution_pauses_for_ambiguous_candidate(self) -> None:
        intent = build_rule_intent("分析华东店铺今年销售额", today=date(2026, 7, 24))
        intent["filter_hints"]["shop_name"] = "华东"
        _resolved, clarifications = resolve_filter_entities(
            "分析华东店铺今年销售额",
            intent,
            {"shop_name": ["华东一店", "华东二店"]},
        )

        self.assertEqual(clarifications[0]["field"], "shop_name")
        self.assertEqual(set(clarifications[0]["candidates"]), {"华东一店", "华东二店"})

    def test_entity_resolution_does_not_silently_drop_unknown_hint(self) -> None:
        intent = build_rule_intent("看火星平台今年销售额", today=date(2026, 7, 24))
        _resolved, clarifications = resolve_filter_entities(
            "看火星平台今年销售额",
            intent,
            {"platform": ["抖音", "天猫"]},
        )

        self.assertEqual(clarifications[0]["field"], "platform")
        self.assertIn("没有找到", clarifications[0]["message"])

    def test_v2_query_respects_top_limit_and_bottom_sort(self) -> None:
        where = "WHERE o.ship_time >= %(start_time)s AND o.ship_time < %(end_time_exclusive)s"
        intent = build_rule_intent("利润最低的前5个产品", today=date(2026, 7, 24))
        plan = build_sql(
            "利润最低的前5个产品",
            where,
            {"start_time": "2026-01-01", "end_time_exclusive": "2026-08-01"},
            intent=intent,
        )

        self.assertTrue(plan["sql"].endswith("LIMIT 5"))
        self.assertIn("ORDER BY profit ASC", plan["sql"])

    def test_v2_normalizer_rejects_empty_allowed_dimensions(self) -> None:
        intent = normalize_analysis_intent_v2(
            {"version": "2", "dimensions": ["DROP TABLE"], "metrics": ["revenue"]},
            "销售额",
            today=date(2026, 7, 24),
        )

        self.assertIsNone(intent)

    def test_confirmed_empty_hint_cancels_rule_detected_entity(self) -> None:
        raw = build_rule_intent("看火星平台今年销售额", today=date(2026, 7, 24))
        raw["filters"]["platform"] = ""
        raw["filter_hints"]["platform"] = ""

        intent = normalize_analysis_intent_v2(raw, "看火星平台今年销售额", today=date(2026, 7, 24))

        self.assertIsNotNone(intent)
        self.assertNotIn("platform", intent["filter_hints"])


if __name__ == "__main__":
    unittest.main()
