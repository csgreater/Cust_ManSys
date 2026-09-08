from __future__ import annotations

import unittest

from app.workbench_store import authorize_report, capture_scope, merge_reviews
from app.import_access import import_batch_access_clause, row_in_scope


def user(user_id=1, shops=None, all_scope=False, permissions=None):
    return {"id": user_id, "username": f"user{user_id}",
            "permissions": set(permissions or ["analytics", "import"]),
            "all_scopes": {"dept": True, "platform": True, "shop": all_scope},
            "scopes": {"dept": [], "platform": [], "shop": shops or ["A"]}}


class ReportScopeTests(unittest.TestCase):
    def test_saved_report_is_denied_when_current_scope_is_narrower(self):
        record = {"owner_id": 1, "access": capture_scope(user(shops=["A", "B"]), {}),
                  "required_permissions": ["analytics"]}
        with self.assertRaises(PermissionError):
            authorize_report(user(shops=["A"]), record)

    def test_report_limited_to_a_shop_survives_unrelated_scope_removal(self):
        record = {"owner_id": 1, "access": capture_scope(user(all_scope=True), {"shop_name": "A"}),
                  "required_permissions": ["analytics"]}
        authorize_report(user(shops=["A"]), record)

    def test_other_owner_and_lost_quality_permission_are_denied(self):
        record = {"owner_id": 1, "access": capture_scope(user(), {}),
                  "required_permissions": ["analytics", "import"]}
        for current in [user(2), user(permissions=["analytics"])]:
            with self.subTest(current=current), self.assertRaises(PermissionError):
                authorize_report(current, record)

    def test_changed_evidence_reopens_a_dismissed_exception(self):
        rows = [{"id": "x", "evidence_hash": "new"}, {"id": "y", "evidence_hash": "same"}]
        reviews = [{"exception_id": "x", "evidence_hash": "old", "status": "dismissed", "note": "old note"},
                   {"exception_id": "y", "evidence_hash": "same", "status": "confirmed", "note": "checked"}]
        merged = merge_reviews(rows, reviews)
        self.assertEqual(merged[0]["status"], "pending")
        self.assertEqual(merged[0]["note"], "")
        self.assertTrue(merged[0]["reopened"])
        self.assertEqual(merged[1]["status"], "confirmed")
        self.assertEqual(merged[1]["note"], "checked")


class ImportAccessTests(unittest.TestCase):
    def test_row_requires_all_scope_dimensions(self):
        current = user()
        self.assertTrue(row_in_scope(current, {"shop_name": "A"}))
        self.assertFalse(row_in_scope(current, {"shop_name": "B"}))

    def test_import_list_checks_owner_and_rejects_whole_out_of_scope_batches(self):
        params = {}
        sql = import_batch_access_clause(user(), params, "l")
        self.assertIn("l.import_user", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("tmp_order_import", sql)
        self.assertIn("shop_name", sql)
        self.assertIn("user1", params.values())


if __name__ == "__main__":
    unittest.main()
