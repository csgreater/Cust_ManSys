from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.main import (
    UnorderedBatchFingerprint,
    attach_revenue_shares,
    mask_sensitive_rows,
    update_batch_fingerprint,
    validate_date_filters,
)


class MainHelperTests(unittest.TestCase):
    def test_date_filters_reject_invalid_reversed_and_oversized_ranges(self) -> None:
        for filters in (
            {"start_time": "bad", "end_time": "2026-07-01"},
            {"start_time": "2026-07-02", "end_time": "2026-07-01"},
            {"start_time": "2020-01-01", "end_time": "2026-07-01"},
        ):
            with self.subTest(filters=filters), self.assertRaises(HTTPException) as raised:
                validate_date_filters(filters)
            self.assertEqual(raised.exception.status_code, 400)

    def test_sensitive_rows_are_masked_before_api_serialization(self) -> None:
        rows = [{"receiver_name": "王小明", "receiver_phone": "13800138000", "receiver_address": "上海市浦东新区世纪大道100号"}]

        result = mask_sensitive_rows(rows)

        self.assertEqual(result[0]["receiver_name"], "王**")
        self.assertEqual(result[0]["receiver_phone"], "138****8000")
        self.assertNotIn("世纪大道", result[0]["receiver_address"])

    def test_revenue_shares_reuse_full_summary_total(self) -> None:
        rows = [{"revenue": 30}, {"revenue": 20}]

        attach_revenue_shares(rows, 100)

        self.assertEqual(float(rows[0]["revenue_share_pct"]), 30.0)
        self.assertEqual(float(rows[1]["revenue_share_pct"]), 20.0)

        attach_revenue_shares(rows, 0)
        self.assertEqual(float(rows[0]["revenue_share_pct"]), 0.0)

    def test_batch_fingerprint_is_order_independent_and_ignores_excel_profit(self) -> None:
        first = {"order_no": "A", "product_no": "P1", "excel_profit": 10}
        second = {"order_no": "B", "product_no": "P2", "excel_profit": 20}
        left = UnorderedBatchFingerprint()
        right = UnorderedBatchFingerprint()

        update_batch_fingerprint(left, first)
        update_batch_fingerprint(left, second)
        second["excel_profit"] = 999
        update_batch_fingerprint(right, second)
        update_batch_fingerprint(right, first)

        self.assertEqual(left.hexdigest(), right.hexdigest())


if __name__ == "__main__":
    unittest.main()
