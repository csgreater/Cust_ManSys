"""One authorization policy for import list, preview, exports and commit."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from app.permissions import has_permission, scope_clause


def row_in_scope(user: dict, row: dict) -> bool:
    return all(
        user.get("all_scopes", {}).get(key)
        or str(row.get(field) or "") in user.get("scopes", {}).get(key, [])
        for key, field in (("dept", "dept"), ("platform", "platform"), ("shop", "shop_name"))
    )


def import_batch_access_clause(user: dict, params: dict, alias: str = "l") -> str:
    if has_permission(user, "admin"):
        return ""
    params["import_owner"] = user["username"]
    where = f" AND {alias}.import_user = %(import_owner)s"
    if all(user.get("all_scopes", {}).get(k) for k in ("dept", "platform", "shop")):
        return where
    tmp_scope = scope_clause(user, params, "access_tmp", "import_tmp_scope")
    saved_scope = scope_clause(user, params, "access_order", "import_saved_scope")
    # Reject the entire batch if any row escapes the user's current scope.
    # Historical committed batches without provenance cannot be safely checked.
    return where + f"""
      AND NOT EXISTS (
        SELECT 1 FROM tmp_order_import access_tmp
        WHERE access_tmp.batch_no = {alias}.batch_no AND NOT (1 = 1 {tmp_scope})
      )
      AND ({alias}.status <> 'committed' OR (
        EXISTS (SELECT 1 FROM t_order_sku_detail lineage WHERE lineage.source_batch_no = {alias}.batch_no)
        AND NOT EXISTS (
          SELECT 1 FROM t_order_sku_detail access_order
          WHERE access_order.source_batch_no = {alias}.batch_no AND NOT (1 = 1 {saved_scope})
        )
      ))
    """


def require_import_batch(conn, user: dict, batch_no: str, *, for_update: bool = False) -> dict[str, Any]:
    if not has_permission(user, "import"):
        raise HTTPException(403, "没有导入权限")
    params = {"batch_no": batch_no}
    clause = import_batch_access_clause(user, params)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT l.* FROM t_import_log l WHERE l.batch_no = %(batch_no)s {clause}"
            + (" FOR UPDATE" if for_update else ""), params,
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "批次不存在或不在当前授权范围内")
    return row
