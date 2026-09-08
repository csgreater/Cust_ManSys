from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app import ark_analytics


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")


class ArkAnalyticsTests(unittest.TestCase):
    def test_parses_v2_json_intent(self) -> None:
        content = {
            "version": "2",
            "analysis_type": "trend",
            "time_range": {"start_time": "2026-01-01", "end_time": "2026-06-30", "label": "今年上半年"},
            "comparison": {"mode": "none"},
            "filters": {},
            "filter_hints": {"platform": "抖音"},
            "dimensions": ["month", "platform"],
            "metrics": ["revenue", "profit_rate"],
            "order_metric": "revenue",
            "wants_share": False,
            "sort_direction": "desc",
            "limit": 10,
            "confidence": 0.93,
            "assumptions": [],
            "clarifications": [],
            "narrative_goal": "查看趋势",
        }
        response = FakeResponse({"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})

        with patch.object(ark_analytics, "ark_analytics_enabled", return_value=True), patch.object(
            ark_analytics, "urlopen", return_value=response
        ):
            intent = ark_analytics.parse_analytics_intent("看抖音平台今年上半年的月度销售额趋势")

        self.assertIsNotNone(intent)
        self.assertEqual(intent["version"], "2")
        self.assertEqual(intent["filter_hints"]["platform"], "抖音")
        self.assertEqual(intent["metrics"], ["revenue", "profit_rate"])

    def test_accepts_json_inside_code_fence(self) -> None:
        content = """```json
{"version":"2","analysis_type":"ranking","dimensions":["shop"],"metrics":["profit"],"order_metric":"profit","confidence":0.9}
```"""
        response = FakeResponse({"choices": [{"message": {"content": content}}]})

        with patch.object(ark_analytics, "ark_analytics_enabled", return_value=True), patch.object(
            ark_analytics, "urlopen", return_value=response
        ):
            intent = ark_analytics.parse_analytics_intent("各店铺利润排行")

        self.assertIsNotNone(intent)
        self.assertEqual(intent["dimensions"], ["shop"])

    def test_provider_timeout_returns_none_for_rule_fallback(self) -> None:
        with patch.object(ark_analytics, "ark_analytics_enabled", return_value=True), patch.object(
            ark_analytics, "urlopen", side_effect=TimeoutError
        ):
            self.assertIsNone(ark_analytics.parse_analytics_intent("各产品销售额"))

    def test_extracts_structured_text_content(self) -> None:
        body = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "第一段"},
                            {"type": "text", "text": "第二段"},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(ark_analytics.extract_message_content(body), "第一段第二段")


if __name__ == "__main__":
    unittest.main()
