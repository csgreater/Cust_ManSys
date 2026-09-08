from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.main import build_analysis_result, prepare_analysis_context


ADMIN_USER = {
    "username": "admin",
    "permissions": {"admin", "analytics"},
    "all_scopes": {"dept": True, "platform": True, "shop": True},
    "scopes": {"dept": [], "platform": [], "shop": []},
}


class AnalysisOrchestrationTests(unittest.TestCase):
    def test_compound_question_resolves_entities_and_builds_safe_plan(self) -> None:
        catalogs = {
            "platform": ["抖音", "天猫"],
            "dept": ["华东", "华南"],
            "category": ["女装", "男装"],
        }
        with patch("app.main.parse_analytics_intent", return_value=None), patch(
            "app.main.load_analysis_catalogs", return_value=catalogs
        ):
            context = asyncio.run(
                prepare_analysis_context(
                    ADMIN_USER,
                    {"question": "看抖音平台华东区域女装今年上半年的销售额、利润率和月度趋势"},
                    allow_clarification=True,
                )
            )

        self.assertFalse(context["clarifications"])
        self.assertEqual(context["parser_source"], "rules")
        self.assertEqual(context["filters"]["platform"], "抖音")
        self.assertEqual(context["filters"]["dept"], "华东")
        self.assertEqual(context["filters"]["category"], "女装")
        self.assertEqual(context["intent"]["dimensions"], ["month"])
        self.assertEqual(len(context["plans"]), 1)
        self.assertIn("o.platform = %(platform)s", context["plans"][0]["sql"])
        self.assertIn("o.dept = %(dept)s", context["plans"][0]["sql"])
        self.assertIn("o.category = %(category)s", context["plans"][0]["sql"])

    def test_unknown_entity_stops_before_query_plan(self) -> None:
        with patch("app.main.parse_analytics_intent", return_value=None), patch(
            "app.main.load_analysis_catalogs", return_value={"platform": ["抖音", "天猫"]}
        ):
            context = asyncio.run(
                prepare_analysis_context(
                    ADMIN_USER,
                    {"question": "看火星平台今年销售额"},
                    allow_clarification=True,
                )
            )

        self.assertEqual(context["clarifications"][0]["field"], "platform")
        self.assertEqual(context["plans"], [])

    def test_confirmed_intent_is_revalidated_and_can_continue(self) -> None:
        confirmed_intent = {
            "version": "2",
            "analysis_type": "ranking",
            "time_range": {"start_time": "2026-01-01", "end_time": "2026-06-30", "label": "上半年"},
            "comparison": {"mode": "none"},
            "filters": {"platform": "抖音"},
            "filter_hints": {"platform": "抖音"},
            "dimensions": ["product"],
            "metrics": ["revenue"],
            "order_metric": "revenue",
            "wants_share": False,
            "sort_direction": "desc",
            "limit": 10,
            "confidence": 1,
            "assumptions": [],
            "clarifications": [],
            "narrative_goal": "产品销售额",
        }
        with patch("app.main.load_analysis_catalogs", return_value={"platform": ["抖音"]}):
            context = asyncio.run(
                prepare_analysis_context(
                    ADMIN_USER,
                    {"question": "看抖音平台产品销售额", "confirmed_intent": confirmed_intent},
                    allow_clarification=True,
                )
            )

        self.assertEqual(context["parser_source"], "confirmed")
        self.assertFalse(context["clarifications"])
        self.assertEqual(context["plans"][0]["params"]["platform"], "抖音")

    def test_final_result_keeps_v2_intent_and_compatibility_fields(self) -> None:
        intent = {
            "version": "2",
            "analysis_type": "ranking",
            "time_range": {"start_time": "2026-01-01", "end_time": "2026-06-30"},
            "comparison": {"mode": "none"},
            "filters": {},
            "dimensions": ["product"],
            "metrics": ["revenue"],
            "order_metric": "revenue",
            "wants_share": False,
            "sort_direction": "desc",
            "limit": 10,
            "confidence": 0.9,
        }
        context = {
            "question": "各产品销售额",
            "filters": {"start_time": "2026-01-01", "end_time": "2026-06-30"},
            "intent": intent,
            "plans": [
                {
                    "key": "current",
                    "label": "当前周期",
                    "sql": "SELECT 1 LIMIT 10",
                    "params": {},
                    "dimensions": ["product"],
                    "metrics": ["revenue"],
                }
            ],
            "parser_source": "rules",
            "ark_enabled": False,
            "warnings": [],
        }
        executed = {
            "rows": [],
            "previous_rows": [],
            "comparison_rows": [],
            "chart": {"type": "bar", "points": []},
            "insights": [],
        }

        result = build_analysis_result(context, executed, "暂无数据", [])

        self.assertIs(result["intent"], intent)
        self.assertEqual(result["parser"], "rules")
        self.assertEqual(result["answer"], "暂无数据")


if __name__ == "__main__":
    unittest.main()
