from __future__ import annotations

import unittest
from fastapi import HTTPException

from app.workbench_api import normalize_filters, select_exception_rows, verify_review_evidence


class WorkbenchApiHelperTests(unittest.TestCase):
    def test_filters_reject_unknown_keys_and_invalid_ranges(self):
        for values in [{"raw_sql": "anything"}, {"start_time": "2026-09-02", "end_time": "2026-09-01"}]:
            with self.subTest(values=values), self.assertRaises(HTTPException):
                normalize_filters(values)

    def test_paging_does_not_hide_the_201st_exception_or_truncate_summary(self):
        rows = [{"id": str(i), "status": "pending", "rule_id": "loss", "rule_label": "亏损", "impact_amount": 1} for i in range(251)]
        page = select_exception_rows(rows, page=5, page_size=50)
        self.assertEqual(page["total"], 251)
        self.assertEqual(page["summary"]["pending"], 251)
        self.assertEqual(page["rows"][0]["id"], "200")
        self.assertEqual(len(page["rows"]), 50)

    def test_invalid_page_is_a_clear_client_error(self):
        with self.assertRaises(HTTPException):
            select_exception_rows([], page=0, page_size=50)

    def test_stale_or_unknown_evidence_cannot_be_reviewed(self):
        rows = [{"id": "a", "evidence_hash": "new"}]
        with self.assertRaises(HTTPException) as raised:
            verify_review_evidence(rows, "a", "old")
        self.assertEqual(raised.exception.status_code, 409)
        with self.assertRaises(HTTPException) as raised:
            verify_review_evidence(rows, "missing", "new")
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
