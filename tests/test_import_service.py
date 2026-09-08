from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook

from app.import_service import HEADER_MAP, parse_excel


class ImportServiceTests(unittest.TestCase):
    def create_workbook(self, directory: Path, values: dict[str, object]) -> Path:
        path = directory / "orders.xlsx"
        workbook = Workbook()
        worksheet = workbook.active
        headers = list(HEADER_MAP)
        worksheet.append(headers)
        worksheet.append([values.get(header, "") for header in headers])
        workbook.save(path)
        workbook.close()
        return path

    def valid_values(self) -> dict[str, object]:
        return {
            "订单编号": "ORDER-001",
            "客户编号": "C-001",
            "渠道分类": "线上",
            "渠道平台": "平台 A",
            "销售渠道": "店铺 A",
            "货品编号": "SKU-001",
            "销售额": 100,
            "成本金额": 50,
            "利润": 50,
            "发货时间": datetime(2026, 7, 1, 10, 0, 0),
        }

    def test_valid_row_is_ready_for_commit(self) -> None:
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), self.valid_values()), batch_no="batch-test")

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.fail_rows, 0)
        self.assertEqual(result.rows[0]["batch_no"], "batch-test")
        self.assertEqual(result.rows[0]["profit"], 50)

    def test_missing_required_value_marks_row_as_invalid(self) -> None:
        values = self.valid_values()
        values["客户编号"] = ""
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-invalid")

        self.assertEqual(result.fail_rows, 1)
        self.assertIn("customer_no不能为空", result.rows[0]["error_message"])

    def test_blank_numeric_required_value_is_not_treated_as_zero(self) -> None:
        values = self.valid_values()
        values["销售额"] = ""
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-blank-revenue")

        self.assertEqual(result.fail_rows, 1)
        self.assertIn("share_receivable不能为空", result.rows[0]["error_message"])

    def test_order_number_and_ship_time_are_required(self) -> None:
        values = self.valid_values()
        values["订单编号"] = ""
        values["发货时间"] = ""
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-missing-identity")

        self.assertEqual(result.fail_rows, 1)
        self.assertIn("order_no不能为空", result.rows[0]["error_message"])
        self.assertIn("ship_time不能为空", result.rows[0]["error_message"])

    def test_non_finite_and_oversized_numbers_are_rejected(self) -> None:
        values = self.valid_values()
        values["销售额"] = "NaN"
        values["成本金额"] = "10000000000"
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-invalid-number")

        self.assertEqual(result.fail_rows, 1)
        self.assertIn("share_receivable必须是有限数字", result.rows[0]["error_message"])
        self.assertIn("cost超出数据库可保存范围", result.rows[0]["error_message"])

    def test_overlong_identifier_is_rejected_without_breaking_staging_shape(self) -> None:
        values = self.valid_values()
        raw_order_no = "ORDER-" + "X" * 123
        values["订单编号"] = raw_order_no
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-long-id")

        row = result.rows[0]
        self.assertEqual(result.fail_rows, 1)
        self.assertEqual(row["order_no"], raw_order_no[:128])
        self.assertIn("order_no长度129超过数据库上限128", row["error_message"])
        self.assertIn(raw_order_no, row["error_message"])

    def test_overlong_sensitive_values_are_not_copied_into_diagnostics(self) -> None:
        for header, field, raw_value, max_length in (
            ("收货人", "receiver_name", "张" * 33, 32),
            ("电话", "receiver_phone", "1" * 33, 32),
            ("地址", "receiver_address", "敏感地址" * 129, 512),
        ):
            with self.subTest(field=field), TemporaryDirectory() as temp:
                values = self.valid_values()
                values[header] = raw_value
                result = parse_excel(
                    self.create_workbook(Path(temp), values),
                    batch_no=f"batch-private-{field}",
                )

            error = result.rows[0]["error_message"]
            self.assertEqual(result.fail_rows, 1)
            self.assertIn(f"{field}长度{len(raw_value)}超过数据库上限{max_length}", error)
            self.assertNotIn(raw_value, error)
            self.assertNotIn("原值：", error)

    def test_decimal_values_with_unstorable_fraction_are_rejected(self) -> None:
        values = self.valid_values()
        values["销售额"] = "100.001"
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-scale")

        self.assertEqual(result.fail_rows, 1)
        self.assertEqual(result.rows[0]["share_receivable"], 0)
        self.assertIn("share_receivable超出数据库小数精度2位", result.rows[0]["error_message"])

    def test_derived_profit_overflow_is_rejected_and_row_remains_storable(self) -> None:
        values = self.valid_values()
        values["销售额"] = "9999999999.99"
        values["成本金额"] = "-9999999999.99"
        values["利润"] = "0"
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-profit-overflow")

        row = result.rows[0]
        self.assertEqual(result.fail_rows, 1)
        self.assertEqual(row["profit"], 0)
        self.assertIn("profit超出数据库可保存范围", row["error_message"])
        self.assertIn("19999999999.98", row["error_message"])

    def test_legitimate_negative_adjustments_keep_current_profit_formula(self) -> None:
        values = self.valid_values()
        values.update(
            {
                "数量": -1,
                "销售额": -100,
                "成本金额": -40,
                "运费": -5,
                "辅料费用": -2,
                "分摊费用": -3,
                "利润": -50,
            }
        )
        with TemporaryDirectory() as temp:
            result = parse_excel(self.create_workbook(Path(temp), values), batch_no="batch-negative-adjustment")

        self.assertEqual(result.fail_rows, 0)
        self.assertEqual(result.rows[0]["profit"], -50)


if __name__ == "__main__":
    unittest.main()
