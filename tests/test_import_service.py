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


if __name__ == "__main__":
    unittest.main()
