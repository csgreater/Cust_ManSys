from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import patch

from app.anomaly_engine import DEFAULT_RULES, build_report, build_snapshot, normalize_rules


ADMIN = {
    "username": "admin",
    "permissions": {"admin", "import", "analytics"},
    "all_scopes": {"dept": True, "platform": True, "shop": True},
    "scopes": {"dept": [], "platform": [], "shop": []},
}


def group(product_no: str, revenue: str, profit: str, fees: str, *, qty: str = "1", rows: int = 1):
    return {
        "dept": "华东",
        "platform": "平台A",
        "shop_name": "门店A",
        "product_no": product_no,
        "category": "食品",
        "product_classification": "常温",
        "product_name": f"商品{product_no}",
        "qty": Decimal(qty),
        "revenue": Decimal(revenue),
        "profit": Decimal(profit),
        "fees": Decimal(fees),
        "express_fee": Decimal("9"),
        "logistics_fee": Decimal("11"),
        "detail_rows": rows,
    }


CURRENT_GROUPS = [
    group("P1", "1000", "-100", "300", qty="10", rows=2),
    group("P2", "2000", "80", "100"),
    group("P3", "1000", "200", "250"),
    group("P4", "1500", "200", "0"),
]
PREVIOUS_GROUPS = [
    group("P1", "1200", "100", "100"),
    group("P2", "1000", "100", "50"),
    group("P3", "1000", "200", "50"),
    group("P5", "1000", "300", "0"),
]


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        params = dict(params or {})
        self.connection.calls.append((sql, params))
        if "anomaly:groups" in sql:
            self.result = self.connection.current_groups if params["start_time"] == "2026-06-01" else self.connection.previous_groups
        elif "anomaly:orders" in sql:
            self.result = {"orders": 4 if params["start_time"] == "2026-06-01" else 5}
        elif "anomaly:quality" in sql:
            self.result = list(self.connection.quality_rows)
        elif "anomaly:latest" in sql:
            self.result = {"latest_data_at": "2026-06-30 18:00:00"}
        else:
            raise AssertionError(f"Unexpected query: {sql}")

    def fetchall(self):
        return list(self.result)

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, quality_rows=(), *, current_groups=None, previous_groups=None):
        self.quality_rows = quality_rows
        self.current_groups = list(CURRENT_GROUPS if current_groups is None else current_groups)
        self.previous_groups = list(PREVIOUS_GROUPS if previous_groups is None else previous_groups)
        self.calls = []

    def cursor(self):
        return FakeCursor(self)


def where_builder(user, filters, alias="o", validate_dates=True):
    if validate_dates and filters["start_time"] == "invalid":
        raise ValueError("invalid date")
    return (
        f" WHERE {alias}.ship_time >= %(start_time)s AND {alias}.ship_time < %(end_time)s",
        {"start_time": filters["start_time"], "end_time": filters["end_time"]},
    )


COMPARISON = {
    "start_time": "2026-05-01",
    "end_time": "2026-05-31",
    "mode": "previous_period",
    "label": "2026-05-01 至 2026-05-31",
}


class AnomalyEngineTests(unittest.TestCase):
    def test_rules_reject_non_finite_negative_and_out_of_range_values(self) -> None:
        self.assertEqual(normalize_rules({}), DEFAULT_RULES)
        for value in (float("nan"), float("inf"), -1, "x", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_rules({"low_margin_pct": value})
        with self.assertRaises(ValueError):
            normalize_rules({"decline_pct": 101})
        with self.assertRaises(ValueError):
            normalize_rules({"unknown": 1})

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_snapshot_uses_complete_union_exact_totals_and_separate_distinct_orders(self, _period) -> None:
        conn = FakeConnection()
        snapshot = build_snapshot(
            conn,
            ADMIN,
            {"start_time": "2026-06-01", "end_time": "2026-06-30"},
            DEFAULT_RULES,
            where_builder,
        )

        self.assertEqual(snapshot["summary"]["revenue"], Decimal("5500"))
        self.assertEqual(snapshot["summary"]["profit"], Decimal("380"))
        self.assertEqual(snapshot["summary"]["qty"], Decimal("13"))
        self.assertEqual(snapshot["summary"]["fees"], Decimal("650"))
        self.assertEqual(snapshot["summary"]["detail_rows"], 5)
        self.assertEqual(snapshot["summary"]["orders"], 4)
        self.assertEqual(snapshot["previous_summary"]["revenue"], Decimal("4200"))
        self.assertEqual(snapshot["previous_summary"]["orders"], 5)
        self.assertEqual(sum(row["revenue_change"] for row in snapshot["contributions"]), Decimal("1300"))
        self.assertEqual(sum(row["profit_change"] for row in snapshot["contributions"]), Decimal("-320"))
        disappeared = next(row for row in snapshot["contributions"] if row["product_no"] == "P5")
        self.assertEqual(disappeared["current_revenue"], Decimal("0"))
        self.assertEqual(disappeared["revenue_change"], Decimal("-1000"))

        group_queries = [sql for sql, _ in conn.calls if "anomaly:groups" in sql]
        order_queries = [sql for sql, _ in conn.calls if "anomaly:orders" in sql]
        self.assertEqual(len(group_queries), 2)
        self.assertEqual(len(order_queries), 2)
        self.assertTrue(all("LIMIT" not in sql.upper() for sql in group_queries))
        self.assertTrue(all("COUNT(DISTINCT o.order_no)" in sql for sql in order_queries))
        self.assertTrue(all("express_fee" not in sql.split(" AS fees")[0].rsplit("SUM(", 1)[-1] for sql in group_queries))

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_snapshot_detects_overlapping_rules_without_claiming_one_total_loss(self, _period) -> None:
        snapshot = build_snapshot(
            FakeConnection(),
            ADMIN,
            {"start_time": "2026-06-01", "end_time": "2026-06-30"},
            DEFAULT_RULES,
            where_builder,
        )
        rules_by_product = {}
        for row in snapshot["operating_rows"]:
            rules_by_product.setdefault(row["product_no"], set()).add(row["rule_id"])

        self.assertTrue({"negative_profit", "low_margin", "high_fee", "profit_decline"}.issubset(rules_by_product["P1"]))
        self.assertIn("revenue_decline", rules_by_product["P5"])
        self.assertIn("profit_decline", rules_by_product["P5"])
        self.assertNotIn("revenue_decline", rules_by_product.get("P4", set()))
        self.assertIn("impact_by_rule", snapshot["summary"])
        self.assertNotIn("total_impact", snapshot["summary"])
        self.assertIn("不代表已验证的业务原因", "".join(snapshot["narrative"]))
        self.assertIn("上升 30.95%", snapshot["narrative"][0])

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_ids_and_evidence_hashes_are_deterministic_and_scoped_to_filters_and_rules(self, _period) -> None:
        filters = {"start_time": "2026-06-01", "end_time": "2026-06-30", "dept": "华东"}
        first = build_snapshot(FakeConnection(), ADMIN, filters, DEFAULT_RULES, where_builder)
        second = build_snapshot(FakeConnection(), ADMIN, dict(filters), dict(DEFAULT_RULES), where_builder)
        self.assertEqual(
            [(r["id"], r["evidence_hash"]) for r in first["operating_rows"]],
            [(r["id"], r["evidence_hash"]) for r in second["operating_rows"]],
        )

        changed_filter = dict(filters, dept="华南")
        third = build_snapshot(FakeConnection(), ADMIN, changed_filter, DEFAULT_RULES, where_builder)
        changed_rules = dict(DEFAULT_RULES, low_margin_pct=6)
        fourth = build_snapshot(FakeConnection(), ADMIN, filters, changed_rules, where_builder)
        self.assertNotEqual(first["operating_rows"][0]["id"], third["operating_rows"][0]["id"])
        self.assertNotEqual(first["operating_rows"][0]["id"], fourth["operating_rows"][0]["id"])
        self.assertNotEqual(first["operating_rows"][0]["evidence_hash"], fourth["operating_rows"][0]["evidence_hash"])

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_quality_rows_require_import_permission_and_ignore_invalid_business_dates(self, _period) -> None:
        quality = [{
            "batch_no": "B001",
            "row_no": 7,
            "error_message": "发货日期格式无效",
            "warning_message": "利润口径不一致",
        }]
        importer = {
            "username": "alice",
            "permissions": {"import"},
            "all_scopes": {"dept": False, "platform": False, "shop": False},
            "scopes": {"dept": ["华东"], "platform": ["平台A"], "shop": ["门店A"]},
        }
        conn = FakeConnection(quality)
        with patch("app.anomaly_engine._comparison_period", return_value=COMPARISON):
            snapshot = build_snapshot(
                conn,
                importer,
                {"start_time": "2026-06-01", "end_time": "2026-06-30", "batch_no": "B001"},
                DEFAULT_RULES,
                where_builder,
            )
        self.assertEqual(len(snapshot["quality_rows"]), 1)
        self.assertEqual(snapshot["quality_rows"][0]["evidence"]["row_no"], 7)
        quality_sql, quality_params = next((sql, params) for sql, params in conn.calls if "anomaly:quality" in sql)
        self.assertNotIn("ship_time", quality_sql)
        self.assertIn("NOT EXISTS", quality_sql)
        self.assertEqual(quality_params["import_owner"], "alice")
        self.assertEqual(quality_params["batch_no"], "B001")

        no_import = dict(importer, permissions={"analytics"})
        denied_conn = FakeConnection(quality)
        denied = build_snapshot(
            denied_conn,
            no_import,
            {"start_time": "2026-06-01", "end_time": "2026-06-30"},
            DEFAULT_RULES,
            where_builder,
        )
        self.assertEqual(denied["quality_rows"], [])
        self.assertFalse(any("anomaly:quality" in sql for sql, _ in denied_conn.calls))

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_build_report_is_deterministic_and_keeps_full_evidence_lists(self, _period) -> None:
        snapshot = build_snapshot(FakeConnection(), ADMIN, {"start_time": "2026-06-01", "end_time": "2026-06-30"}, DEFAULT_RULES, where_builder)
        first = build_report(snapshot, "monthly", "六月经营报告")
        second = build_report(snapshot, "monthly", "六月经营报告")
        self.assertEqual(first, second)
        self.assertEqual(first["operating_rows"], snapshot["operating_rows"])
        self.assertEqual(first["quality_rows"], snapshot["quality_rows"])
        self.assertTrue(any(section.get("top_n") == 10 for section in first["sections"]))
        with self.assertRaises(ValueError):
            build_report(snapshot, "unsupported", "bad")

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_data_version_does_not_change_when_database_returns_groups_in_reverse_order(self, _period) -> None:
        filters = {"start_time": "2026-06-01", "end_time": "2026-06-30"}
        normal = build_snapshot(FakeConnection(), ADMIN, filters, DEFAULT_RULES, where_builder)
        reversed_rows = build_snapshot(
            FakeConnection(current_groups=reversed(CURRENT_GROUPS), previous_groups=reversed(PREVIOUS_GROUPS)),
            ADMIN, filters, DEFAULT_RULES, where_builder,
        )
        self.assertEqual(normal["data_version"], reversed_rows["data_version"])

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_quality_diagnostics_hide_legacy_sensitive_values_before_hashing(self, _period) -> None:
        secret = "上海市浦东新区世纪大道100号"
        quality = [{
            "batch_no": "B-PII", "row_no": 3,
            "error_message": f"receiver_name长度3校验失败，原值：王小明；receiver_address格式错误，原值：{secret}；receiver_phone原值：13800138000",
            "warning_message": "联系电话 13900139000",
        }]
        snapshot = build_snapshot(
            FakeConnection(quality), ADMIN,
            {"start_time": "2026-06-01", "end_time": "2026-06-30", "batch_no": "B-PII"},
            DEFAULT_RULES, where_builder,
        )
        row = snapshot["quality_rows"][0]
        visible = f"{row['message']} {row['current_value']} {row['evidence']}"
        self.assertNotIn("王小明", visible)
        self.assertNotIn(secret, visible)
        self.assertNotIn("13800138000", visible)
        self.assertNotIn("13900139000", visible)
        self.assertIn("139****9000", visible)
        self.assertIn("[已隐藏]", visible)

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_empty_current_period_does_not_turn_all_previous_groups_into_confirmed_declines(self, _period) -> None:
        snapshot = build_snapshot(
            FakeConnection(current_groups=[], previous_groups=PREVIOUS_GROUPS), ADMIN,
            {"start_time": "2026-06-01", "end_time": "2026-06-30"}, DEFAULT_RULES, where_builder,
        )
        decline_rules = {"revenue_decline", "profit_decline"}
        self.assertFalse(any(row["rule_id"] in decline_rules for row in snapshot["operating_rows"]))
        text = "".join(snapshot["warnings"] + snapshot["narrative"])
        self.assertIn("本期无经营记录", text)
        self.assertIn("无法确认零经营还是未导入", text)
        self.assertIsNone(snapshot["summary"]["profit_rate"])
        self.assertIsNone(snapshot["summary"]["fee_rate"])
        self.assertEqual(sum(row["revenue_change"] for row in snapshot["contributions"]), Decimal("-4200"))

    @patch("app.anomaly_engine._comparison_period", return_value=COMPARISON)
    def test_percentage_rule_severity_compares_money_with_revenue_not_percentage_points(self, _period) -> None:
        current = [
            group("LM", "1000000", "49990", "0"),
            group("HF", "1000000", "100000", "200010"),
        ]
        snapshot = build_snapshot(
            FakeConnection(current_groups=current, previous_groups=[]), ADMIN,
            {"start_time": "2026-06-01", "end_time": "2026-06-30"}, DEFAULT_RULES, where_builder,
        )
        selected = {row["rule_id"]: row for row in snapshot["operating_rows"]}
        self.assertEqual(selected["low_margin"]["impact_amount"], Decimal("10"))
        self.assertEqual(selected["low_margin"]["severity"], "medium")
        self.assertEqual(selected["high_fee"]["impact_amount"], Decimal("10"))
        self.assertEqual(selected["high_fee"]["severity"], "medium")


if __name__ == "__main__":
    unittest.main()
