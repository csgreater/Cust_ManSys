"""HTTP boundary for scoped exception analysis and immutable reports."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
from typing import Literal

import pymysql
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.db import connection
from app.permissions import has_permission
from app import workbench_store as store

router = APIRouter()
FILTER_KEYS = {"start_time", "end_time", "dept", "platform", "shop_name", "category",
               "product_classification", "product", "order_no", "province", "city", "order_source",
               "comparison_mode", "batch_no"}


def api_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except pymysql.Error as exc:
            raise HTTPException(503, "工作台存储暂不可用，请检查数据库连接与工作台迁移状态") from exc
    return wrapped


def current_user(request, permission="analytics"):
    from app.main import require_api_user
    return require_api_user(request, permission)


def ok(data):
    return JSONResponse({"ok": True, "data": jsonable_encoder(data)})


def normalize_filters(values: dict) -> dict:
    from app.main import last_month_range, validate_date_filters
    if not isinstance(values, dict) or set(values) - FILTER_KEYS:
        raise HTTPException(400, "筛选包含不支持的字段")
    start, end = last_month_range()
    filters = {k: "" for k in FILTER_KEYS}
    filters.update(start_time=start, end_time=end, comparison_mode="previous_period")
    for key, value in values.items():
        if not isinstance(value, str) or len(value) > 512:
            raise HTTPException(400, "筛选值必须是长度不超过 512 的文本")
        filters[key] = value.strip()
    if filters["comparison_mode"] not in {"previous_period", "year_over_year"}:
        raise HTTPException(400, "不支持的比较模式")
    validate_date_filters(filters)
    # Date arithmetic for previous periods and exclusive bounds must remain representable.
    if filters["start_time"] < "1001-01-01" or filters["end_time"] > "9998-12-31":
        raise HTTPException(400, "日期超出支持范围")
    return filters


def query_filters(request):
    return normalize_filters({k: v for k, v in request.query_params.items() if k in FILTER_KEYS})


def select_exception_rows(rows, *, page=1, page_size=50, rule_id="", status=""):
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(400, "页码必须大于零，每页数量为 1–200")
    if status not in {"", "pending", "confirmed", "dismissed"}:
        raise HTTPException(400, "无效核查状态")
    selected = [r for r in rows if (not rule_id or r["rule_id"] == rule_id) and (not status or r["status"] == status)]
    grouped = {}
    for row in selected:
        group = grouped.setdefault(row["rule_id"], {"rule_id": row["rule_id"], "rule_label": row["rule_label"], "count": 0, "impact_amount": Decimal("0")})
        group["count"] += 1
        group["impact_amount"] += Decimal(str(row.get("impact_amount") or 0))
    summary = {"total": len(selected), **{s: sum(r["status"] == s for r in selected) for s in ("pending", "confirmed", "dismissed")},
               "by_rule": list(grouped.values()), "impact_note": "各规则可能涉及相同对象，影响金额按规则分别展示，不相加作为总损失。"}
    return {"rows": selected[(page-1)*page_size:page*page_size], "total": len(selected), "page": page,
            "page_size": page_size, "summary": summary}


def verify_review_evidence(rows, exception_id, evidence_hash):
    row = next((r for r in rows if r["id"] == exception_id), None)
    if row is None:
        raise HTTPException(404, "异常不存在或已解除，请刷新列表")
    if row["evidence_hash"] != evidence_hash:
        raise HTTPException(409, "异常数据已变化，请刷新证据后重新核查")
    return row


def snapshot(conn, user, filters):
    from app.main import order_where
    from app.anomaly_engine import DEFAULT_RULES, build_snapshot, normalize_rules
    rules, _ = store.load_rules(conn, DEFAULT_RULES)
    result = build_snapshot(conn, user, filters, normalize_rules(rules), order_where)
    reviews = store.load_reviews(conn, user["id"])
    for key in ("operating_rows", "quality_rows"):
        result[key] = store.merge_reviews(result.get(key, []), reviews)
    visible_reviews = [{k: row.get(k) for k in ("id", "evidence_hash", "status", "note")}
                       for row in result["operating_rows"] + result["quality_rows"]]
    result["data_version"] = "data-" + store.digest({"source": result["data_version"],
                                                     "reviews": sorted(visible_reviews, key=lambda r: r["id"])})[:20]
    return result


def require_type(user, exception_type):
    if exception_type not in {"operating", "quality"}:
        raise HTTPException(400, "不支持的异常类型")
    if exception_type == "quality" and not has_permission(user, "import"):
        raise HTTPException(403, "查看数据质量异常需要导入权限")


def download(content, filename, content_type):
    return Response(content, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


class RulesPayload(BaseModel):
    rules: dict


class ReviewPayload(BaseModel):
    filters: dict[str, str] = Field(default_factory=dict)
    type: Literal["operating", "quality"] = "operating"
    id: str = Field(min_length=1, max_length=64)
    evidence_hash: str = Field(min_length=1, max_length=64)
    status: Literal["pending", "confirmed", "dismissed"]
    note: str = Field(default="", max_length=2000)


class ReportPayload(BaseModel):
    filters: dict[str, str] = Field(default_factory=dict)
    report_type: Literal["monthly", "exception"] = "monthly"
    title: str = Field(default="", max_length=200)


@router.get("/api/workbench/rules")
@api_errors
def get_rules(request: Request):
    current_user(request)
    from app.anomaly_engine import DEFAULT_RULES
    with connection() as conn:
        rules, version = store.load_rules(conn, DEFAULT_RULES)
    return ok({"rules": rules, "version": version})


@router.put("/api/workbench/rules")
@api_errors
def put_rules(request: Request, payload: RulesPayload):
    user = current_user(request, "settings")
    from app.anomaly_engine import normalize_rules
    rules = normalize_rules(payload.rules)
    with connection() as conn:
        version = store.save_rules(conn, rules, user["id"])
    return ok({"rules": rules, "version": version})


@router.get("/api/workbench/context")
@api_errors
def get_context(request: Request):
    user = current_user(request, "view")
    from app.main import order_where
    from app.anomaly_engine import DEFAULT_RULES
    filters = query_filters(request)
    where, params = order_where(user, filters, validate_dates=False, include_dates=False)
    with connection() as conn:
        rules, version = store.load_rules(conn, DEFAULT_RULES)
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(o.ship_time) AS latest_data_at, MAX(o.update_time) AS updated_at FROM t_order_sku_detail o {where}", params)
            latest = cur.fetchone()
            catalogs = {}
            for field in ("dept", "platform", "shop_name", "province", "city", "order_source"):
                candidate_filters = {**filters, field: ""}
                candidate_where, candidate_params = order_where(user, candidate_filters, validate_dates=False, include_dates=False)
                cur.execute(f"SELECT DISTINCT o.{field} AS value FROM t_order_sku_detail o {candidate_where} AND o.{field} <> '' ORDER BY o.{field}", candidate_params)
                catalogs[field] = [r["value"] for r in cur.fetchall()]
    period = None
    if latest.get("latest_data_at"):
        value = latest["latest_data_at"].date()
        first = value.replace(day=1)
        next_month = date(first.year + (first.month == 12), 1 if first.month == 12 else first.month + 1, 1)
        period = {"start_time": first.isoformat(), "end_time": (next_month-timedelta(days=1)).isoformat()}
    return ok({"latest_period": period, "latest_data_at": latest.get("latest_data_at"),
               "latest_import_at": latest.get("updated_at"), "rules": rules, "rules_version": version, "catalogs": catalogs})


@router.get("/api/exceptions")
@api_errors
def get_exceptions(request: Request, type: str = "operating", page: int = 1, page_size: int = 50, rule_id: str = "", status: str = ""):
    user = current_user(request, "import" if type == "quality" else "analytics")
    require_type(user, type)
    filters = query_filters(request)
    with connection() as conn:
        result = snapshot(conn, user, filters)
    selected = select_exception_rows(result[type+"_rows"], page=page, page_size=page_size, rule_id=rule_id, status=status)
    selected.update({k: result.get(k) for k in ("rules", "rules_version", "data_version", "comparison", "warnings")})
    selected["filters"] = filters
    return ok(selected)


@router.post("/api/exceptions/review")
@api_errors
def review_exception(request: Request, payload: ReviewPayload):
    user = current_user(request, "import" if payload.type == "quality" else "analytics")
    require_type(user, payload.type)
    with connection() as conn:
        result = snapshot(conn, user, normalize_filters(payload.filters))
        row = verify_review_evidence(result[payload.type+"_rows"], payload.id, payload.evidence_hash)
        store.save_review(conn, user["id"], row, payload.status, payload.note)
    return ok({"id": payload.id, "status": payload.status, "note": payload.note.strip()})


@router.get("/api/exceptions/export.xlsx")
@api_errors
def export_exceptions(request: Request, type: str = "operating", rule_id: str = "", status: str = ""):
    user = current_user(request, "import" if type == "quality" else "analytics")
    if not has_permission(user, "export") and type != "quality":
        raise HTTPException(403, "没有导出权限")
    require_type(user, type)
    from app.report_exports import export_exceptions_xlsx
    with connection() as conn:
        result = snapshot(conn, user, query_filters(request))
    rows = result[type+"_rows"]
    select_exception_rows(rows, rule_id=rule_id, status=status)  # validate selection values
    rows = [r for r in rows if (not rule_id or r["rule_id"] == rule_id) and (not status or r["status"] == status)]
    return download(export_exceptions_xlsx(rows), "exceptions.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def public_report(report, *, stale=False):
    return {**report.get("body", {}), **{k: v for k, v in report.items() if k not in {"access", "required_permissions", "owner_id"}}, "stale": stale}


def create_report(conn, user, filters, report_type, title):
    from app.anomaly_engine import build_report
    result = snapshot(conn, user, filters)
    body = build_report(result, report_type, title or f"{filters['start_time']} 至 {filters['end_time']} {'经营报告' if report_type == 'monthly' else '异常专题报告'}")
    required = ["analytics"] + (["import"] if body.get("quality_rows") else [])
    batches = sorted({r["evidence"]["batch_no"] for r in body.get("quality_rows", [])})
    if batches and has_permission(user, "admin"):
        # A global importer may see somebody else's batch. Preserve this access
        # requirement even if the account later keeps the same business scopes.
        params = {"owner": user["username"], **{f"batch_{i}": b for i, b in enumerate(batches)}}
        placeholders = ",".join(f"%(batch_{i})s" for i in range(len(batches)))
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS other_owners FROM t_import_log WHERE batch_no IN ({placeholders}) AND import_user <> %(owner)s", params)
            if cur.fetchone()["other_owners"]:
                required.append("admin")
    return store.save_report(conn, user, body, required)


@router.get("/api/reports")
@api_errors
def reports_list(request: Request):
    user = current_user(request)
    with connection() as conn:
        reports = store.list_reports(conn, user)
    return ok({"reports": [public_report(r) for r in reports]})


@router.post("/api/reports")
@api_errors
def reports_create(request: Request, payload: ReportPayload):
    user = current_user(request)
    with connection() as conn:
        report = create_report(conn, user, normalize_filters(payload.filters), payload.report_type, payload.title)
    return ok(public_report(report))


@router.get("/api/reports/{report_id}")
@api_errors
def reports_get(request: Request, report_id: str):
    user = current_user(request)
    with connection() as conn:
        report = store.get_report(conn, user, report_id)
        current = snapshot(conn, user, report["filters"])
    stale = report["data_version"] != current["data_version"] or report["rules_version"] != current["rules_version"]
    return ok(public_report(report, stale=stale))


@router.post("/api/reports/{report_id}/regenerate")
@api_errors
def reports_regenerate(request: Request, report_id: str):
    user = current_user(request)
    with connection() as conn:
        previous = store.get_report(conn, user, report_id)
        report = create_report(conn, user, previous["filters"], previous["report_type"], previous["title"])
    return ok(public_report(report))


@router.get("/api/reports/{report_id}/export.xlsx")
@api_errors
def report_xlsx(request: Request, report_id: str):
    user = current_user(request)
    if not has_permission(user, "export"):
        raise HTTPException(403, "没有导出权限")
    from app.report_exports import export_report_xlsx
    with connection() as conn:
        report = store.get_report(conn, user, report_id)
    return download(export_report_xlsx(public_report(report)), f"report-v{report['version']}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/api/reports/{report_id}/export.pdf")
@api_errors
def report_pdf(request: Request, report_id: str):
    user = current_user(request)
    if not has_permission(user, "export"):
        raise HTTPException(403, "没有导出权限")
    from app.report_exports import export_report_pdf
    with connection() as conn:
        report = store.get_report(conn, user, report_id)
    return download(export_report_pdf(public_report(report)), f"report-v{report['version']}.pdf", "application/pdf")


@router.get("/api/imports/{batch_no}/errors/export.xlsx")
@api_errors
def import_error_export(request: Request, batch_no: str):
    user = current_user(request, "import")
    from app.import_access import require_import_batch
    from app.report_exports import export_exceptions_xlsx
    with connection() as conn:
        require_import_batch(conn, user, batch_no)
        result = snapshot(conn, user, normalize_filters({"batch_no": batch_no}))
    return download(export_exceptions_xlsx(result["quality_rows"]), "import-errors.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/api/imports/{batch_no}/recover")
@api_errors
def import_recover(request: Request, batch_no: str):
    user = current_user(request, "import")
    from app.import_lifecycle import recover_stale_batch
    with connection() as conn:
        result = recover_stale_batch(conn, user, batch_no)
    return ok(result)
