from __future__ import annotations

import csv
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, settings
from app.db import connection
from app.import_service import HEADER_MAP, ImportParseResult, parse_excel
from app.permissions import has_permission, load_user_context, requested_scope_filters, scope_clause
from app.security import verify_password


settings.validate_for_runtime()

app = FastAPI(title="订单数据管理系统")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site=settings.session_same_site,
    https_only=settings.secure_cookies,
    max_age=settings.session_max_age,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")
UPLOAD_CHUNK_SIZE = 1024 * 1024


LEGACY_HTML_ROUTES = {
    "/login",
    "/dashboard",
    "/orders",
    "/imports",
    "/analytics/products",
    "/analytics/shops",
    "/settings/users",
    "/settings/roles",
}


@app.middleware("http")
async def prefer_vue_frontend(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    accepts_html = "text/html" in request.headers.get("accept", "")
    legacy_import_detail = path.startswith("/imports/") and request.method == "GET"
    if (
        FRONTEND_DIST.exists()
        and request.method == "GET"
        and accepts_html
        and (path in LEGACY_HTML_ROUTES or legacy_import_detail)
    ):
        return RedirectResponse("/ui/", status_code=303)
    return await call_next(request)


def month_range() -> tuple[str, str]:
    today = date.today()
    start = today.replace(day=1)
    end = add_months(start, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def last_month_range() -> tuple[str, str]:
    this_month = date.today().replace(day=1)
    start = add_months(this_month, -1)
    end = this_month - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def render(request: Request, template: str, context: dict[str, Any]) -> HTMLResponse:
    context.setdefault("request", request)
    context.setdefault("current_path", request.url.path)
    return templates.TemplateResponse(template, context)


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def current_user(request: Request) -> dict[str, Any] | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with connection() as conn:
        return load_user_context(conn, int(user_id))


def require_user(request: Request, permission: str | None = None) -> dict[str, Any] | RedirectResponse:
    user = current_user(request)
    if not user:
        return redirect("/login")
    if permission and not has_permission(user, permission):
        raise HTTPException(status_code=403, detail="没有权限访问该功能")
    return user


def require_api_user(request: Request, permission: str | None = None) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    if permission and not has_permission(user, permission):
        raise HTTPException(status_code=403, detail="没有权限访问该功能")
    return user


def api_ok(data: Any = None, **extra: Any) -> JSONResponse:
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return JSONResponse(jsonable_encoder(payload))


def default_filters(request: Request) -> dict[str, Any]:
    start, end = last_month_range()
    return {
        "start_time": request.query_params.get("start_time", start),
        "end_time": request.query_params.get("end_time", end),
        "dept": request.query_params.get("dept", ""),
        "platform": request.query_params.get("platform", ""),
        "shop_name": request.query_params.get("shop_name", ""),
        "category": request.query_params.get("category", ""),
        "product": request.query_params.get("product", ""),
        "order_no": request.query_params.get("order_no", ""),
    }


def order_where(user: dict[str, Any], filters: dict[str, Any], alias: str = "o") -> tuple[str, dict[str, Any]]:
    params = dict(filters)
    try:
        params["end_time_exclusive"] = (datetime.strptime(filters["end_time"], "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    except (TypeError, ValueError):
        params["end_time_exclusive"] = filters["end_time"]
    clauses = [
        f"{alias}.ship_time >= %(start_time)s",
        f"{alias}.ship_time < %(end_time_exclusive)s",
    ]
    if filters.get("category"):
        clauses.append(f"{alias}.category = %(category)s")
    if filters.get("product"):
        clauses.append(f"({alias}.product_name LIKE %(product_like)s OR {alias}.product_no LIKE %(product_like)s OR {alias}.sku_id LIKE %(product_like)s)")
        params["product_like"] = f"%{filters['product']}%"
    if filters.get("order_no"):
        clauses.append(f"{alias}.order_no LIKE %(order_no_like)s")
        params["order_no_like"] = f"%{filters['order_no']}%"
    scope_filter, params = requested_scope_filters(params, alias)
    where = " WHERE " + " AND ".join(clauses) + scope_filter + scope_clause(user, params, alias)
    return where, params


def mask_phone(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) < 7:
        return "***"
    return f"{text[:3]}****{text[-4:]}"


def mask_name(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    return text[0] + "**" if len(text) > 1 else "*"


templates.env.filters["phone_mask"] = mask_phone
templates.env.filters["name_mask"] = mask_name


async def save_upload_to_temp(file: UploadFile) -> Path:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="请上传 xlsx 或 xlsm 文件")

    suffix = Path(file.filename).suffix
    total = 0
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail=f"上传文件不能超过 {settings.max_upload_mb}MB")
                tmp.write(chunk)
        return tmp_path
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get("/healthz")
def healthz():
    return {"ok": True, "env": settings.app_env}


@app.get("/readyz")
def readyz():
    try:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"ok": True, "database": "ready"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if FRONTEND_DIST.exists():
        return redirect("/ui/")
    if current_user(request):
        return redirect("/dashboard")
    return redirect("/login")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return redirect("/dashboard")
    return render(request, "login.html", {"error": ""})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM t_user WHERE username = %(username)s AND is_active = 1", {"username": username})
            user = cur.fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return render(request, "login.html", {"error": "账号或密码错误"})
    request.session["user_id"] = user["id"]
    return redirect("/dashboard")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return redirect("/login")


@app.get("/api/me")
def api_me(request: Request):
    user = current_user(request)
    if not user:
        return api_ok({"authenticated": False})
    return api_ok(
        {
            "authenticated": True,
            "username": user["username"],
            "display_name": user["display_name"],
            "permissions": sorted(user["permissions"]),
            "role_codes": sorted(user["role_codes"]),
            "scopes": user["scopes"],
            "all_scopes": user["all_scopes"],
        }
    )


@app.post("/api/login")
def api_login(request: Request, username: str = Form(...), password: str = Form(...)):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM t_user WHERE username = %(username)s AND is_active = 1", {"username": username})
            user = cur.fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    request.session["user_id"] = user["id"]
    return api_me(request)


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return api_ok()


@app.get("/api/dashboard")
def api_dashboard(request: Request):
    user = require_api_user(request, "view")
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  COALESCE(SUM(o.share_receivable),0) AS revenue,
                  COALESCE(SUM(o.qty),0) AS qty,
                  COALESCE(SUM(o.profit),0) AS profit,
                  COUNT(DISTINCT o.order_no) AS orders
                FROM t_order_sku_detail o
                {where}
                """,
                params,
            )
            summary = cur.fetchone()
            cur.execute(
                f"""
                SELECT o.product_no, o.product_name, o.category,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.profit) AS profit
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.product_no, o.product_name, o.category
                ORDER BY revenue DESC
                LIMIT 8
                """,
                params,
            )
            top_products = list(cur.fetchall())
    revenue = Decimal(summary["revenue"] or 0)
    profit = Decimal(summary["profit"] or 0)
    summary["profit_rate"] = (profit / revenue * 100) if revenue else Decimal("0")
    return api_ok({"filters": filters, "summary": summary, "top_products": top_products})


@app.get("/api/orders")
def api_orders(request: Request):
    user = require_api_user(request, "view")
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.*
                FROM t_order_sku_detail o
                {where}
                ORDER BY o.ship_time DESC, o.id DESC
                LIMIT 200
                """,
                params,
            )
            rows = list(cur.fetchall())
    return api_ok({"filters": filters, "rows": rows})


@app.get("/api/analytics/products")
def api_products(request: Request):
    user = require_api_user(request, "analytics")
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.product_no, o.product_name, o.category,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.cost) AS cost,
                       SUM(o.profit) AS profit,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.product_no, o.product_name, o.category
                ORDER BY revenue DESC
                LIMIT 100
                """,
                params,
            )
            rows = list(cur.fetchall())
            cur.execute(
                f"""
                SELECT o.category,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.cost) AS cost,
                       SUM(o.profit) AS profit,
                       COUNT(DISTINCT o.product_no) AS product_count,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.category
                ORDER BY revenue DESC
                LIMIT 30
                """,
                params,
            )
            category_rows = list(cur.fetchall())
    return api_ok({"filters": filters, "rows": rows, "category_rows": category_rows})


@app.get("/api/analytics/shops")
def api_shops(request: Request):
    user = require_api_user(request, "analytics")
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.platform, o.shop_name,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.profit) AS profit,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.platform, o.shop_name
                ORDER BY revenue DESC
                LIMIT 100
                """,
                params,
            )
            rows = list(cur.fetchall())
    return api_ok({"filters": filters, "rows": rows})


@app.get("/api/imports")
def api_imports(request: Request):
    require_api_user(request, "import")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM t_import_log ORDER BY import_time DESC LIMIT 50")
            logs = list(cur.fetchall())
    return api_ok({"logs": logs})


@app.post("/api/imports/upload")
async def api_import_upload(request: Request, file: UploadFile = File(...)):
    user = require_api_user(request, "import")
    tmp_path = await save_upload_to_temp(file)
    try:
        result = parse_excel(tmp_path)
        save_import_batch(result, file.filename, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except PermissionError:
            pass
    return api_ok({"batch_no": result.batch_no})


@app.get("/api/imports/{batch_no}")
def api_import_detail(request: Request, batch_no: str):
    require_api_user(request, "import")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM t_import_log WHERE batch_no = %(batch_no)s", {"batch_no": batch_no})
            log = cur.fetchone()
            if not log:
                raise HTTPException(status_code=404, detail="导入批次不存在")
            cur.execute(
                """
                SELECT *
                FROM tmp_order_import
                WHERE batch_no = %(batch_no)s
                ORDER BY COALESCE(error_message, '') <> '' DESC, row_no ASC
                LIMIT 200
                """,
                {"batch_no": batch_no},
            )
            rows = list(cur.fetchall())
    return api_ok({"log": log, "rows": rows})


@app.post("/api/imports/{batch_no}/commit")
def api_import_commit(request: Request, batch_no: str):
    response = import_commit(request, batch_no)
    if isinstance(response, RedirectResponse):
        return api_ok({"batch_no": batch_no})
    return response


@app.get("/api/settings/users")
def api_settings_users(request: Request):
    require_api_user(request, "settings")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.display_name, u.is_active,
                       GROUP_CONCAT(r.role_name ORDER BY r.id SEPARATOR ' / ') AS roles
                FROM t_user u
                LEFT JOIN t_user_role ur ON ur.user_id = u.id
                LEFT JOIN t_role r ON r.id = ur.role_id
                GROUP BY u.id, u.username, u.display_name, u.is_active
                ORDER BY u.id
                """
            )
            users = list(cur.fetchall())
    return api_ok({"users": users})


@app.get("/api/settings/roles")
def api_settings_roles(request: Request):
    require_api_user(request, "settings")
    return api_ok({"roles": load_roles_with_scopes()})


@app.post("/api/settings/roles")
def api_update_role_scope(
    request: Request,
    role_id: int = Form(...),
    dept_scope: str = Form("*"),
    platform_scope: str = Form("*"),
    shop_scope: str = Form("*"),
):
    require_api_user(request, "settings")
    scope_values = {
        "dept": split_scope(dept_scope),
        "platform": split_scope(platform_scope),
        "shop": split_scope(shop_scope),
    }
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM t_role_data_scope WHERE role_id = %(role_id)s", {"role_id": role_id})
            records = []
            for scope_type, values in scope_values.items():
                for value in values:
                    records.append({"role_id": role_id, "scope_type": scope_type, "scope_value": value})
            if records:
                cur.executemany(
                    """
                    INSERT INTO t_role_data_scope (role_id, scope_type, scope_value)
                    VALUES (%(role_id)s, %(scope_type)s, %(scope_value)s)
                    """,
                    records,
                )
    return api_ok({"roles": load_roles_with_scopes()})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request, "view")
    if isinstance(user, RedirectResponse):
        return user
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  COALESCE(SUM(o.share_receivable),0) AS revenue,
                  COALESCE(SUM(o.qty),0) AS qty,
                  COALESCE(SUM(o.profit),0) AS profit,
                  COUNT(DISTINCT o.order_no) AS orders
                FROM t_order_sku_detail o
                {where}
                """,
                params,
            )
            summary = cur.fetchone()
            cur.execute(
                f"""
                SELECT o.product_no, o.product_name,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.profit) AS profit
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.product_no, o.product_name
                ORDER BY revenue DESC
                LIMIT 8
                """,
                params,
            )
            top_products = list(cur.fetchall())
    revenue = Decimal(summary["revenue"] or 0)
    profit = Decimal(summary["profit"] or 0)
    summary["profit_rate"] = (profit / revenue * 100) if revenue else Decimal("0")
    return render(request, "dashboard.html", {"user": user, "filters": filters, "summary": summary, "top_products": top_products})


@app.get("/orders", response_class=HTMLResponse)
def orders(request: Request):
    user = require_user(request, "view")
    if isinstance(user, RedirectResponse):
        return user
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.*
                FROM t_order_sku_detail o
                {where}
                ORDER BY o.ship_time DESC, o.id DESC
                LIMIT 200
                """,
                params,
            )
            rows = list(cur.fetchall())
    return render(request, "orders.html", {"user": user, "filters": filters, "rows": rows})


@app.get("/orders/export")
def orders_export(request: Request):
    user = require_user(request, "export")
    if isinstance(user, RedirectResponse):
        return user
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT order_no, sku_id, order_source, customer_no, customer_name, dept, platform, shop_name,
                       category, product_name, product_no, unit, qty, share_receivable,
                       province, city, district, ship_time, cost, express_fee, logistics_fee,
                       freight, aux_material, share_cost, profit
                FROM t_order_sku_detail o
                {where}
                ORDER BY o.ship_time DESC
                LIMIT 50000
                """,
                params,
            )
            rows = list(cur.fetchall())

    def iter_csv():
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        headers = list(rows[0].keys()) if rows else ["empty"]
        writer.writerow(headers)
        yield "\ufeff" + buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for row in rows:
            writer.writerow([row[h] for h in headers])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"orders_{datetime.now():%Y%m%d%H%M%S}.csv"
    return StreamingResponse(iter_csv(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/imports", response_class=HTMLResponse)
def imports_page(request: Request):
    user = require_user(request, "import")
    if isinstance(user, RedirectResponse):
        return user
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM t_import_log ORDER BY import_time DESC LIMIT 50")
            logs = list(cur.fetchall())
    return render(request, "imports.html", {"user": user, "logs": logs, "error": ""})


@app.post("/imports/upload", response_class=HTMLResponse)
async def upload_import(request: Request, file: UploadFile = File(...)):
    user = require_user(request, "import")
    if isinstance(user, RedirectResponse):
        return user
    tmp_path: Path | None = None
    try:
        tmp_path = await save_upload_to_temp(file)
        result = parse_excel(tmp_path)
        save_import_batch(result, file.filename, user)
    except HTTPException as exc:
        return render(request, "imports.html", {"user": user, "logs": [], "error": str(exc.detail)})
    except Exception as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        return render(request, "imports.html", {"user": user, "logs": [], "error": str(exc)})
    tmp_path.unlink(missing_ok=True)
    return redirect(f"/imports/{result.batch_no}")


def save_import_batch(result: ImportParseResult, filename: str, user: dict[str, Any]) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tmp_order_import WHERE batch_no = %(batch_no)s", {"batch_no": result.batch_no})
            if result.rows:
                columns = [
                    "batch_no",
                    "row_no",
                    "link_id",
                    "sku_id",
                    "order_source",
                    "customer_no",
                    "customer_name",
                    "dept",
                    "platform",
                    "shop_name",
                    "order_no",
                    "original_order_no",
                    "logistics_type",
                    "logistics_no",
                    "receiver_name",
                    "receiver_phone",
                    "category",
                    "product_name",
                    "product_no",
                    "unit",
                    "qty",
                    "share_receivable",
                    "province",
                    "city",
                    "district",
                    "ship_time",
                    "cost",
                    "express_fee",
                    "logistics_fee",
                    "freight",
                    "aux_material",
                    "share_cost",
                    "excel_profit",
                    "profit",
                    "error_message",
                    "warning_message",
                ]
                placeholders = ",".join([f"%({column})s" for column in columns])
                cur.executemany(
                    f"INSERT INTO tmp_order_import ({','.join(columns)}) VALUES ({placeholders})",
                    result.rows,
                )
                cur.execute(
                    """
                    UPDATE tmp_order_import t
                    INNER JOIN t_order_sku_detail o
                      ON o.order_no = t.order_no
                     AND o.ship_time = t.ship_time
                     AND (
                       (t.sku_id <> '' AND o.sku_id = t.sku_id)
                       OR (t.sku_id = '' AND o.product_no = t.product_no)
                     )
                    SET t.error_message = TRIM(BOTH '; ' FROM CONCAT_WS('; ', NULLIF(t.error_message, ''), '与历史数据重复'))
                    WHERE t.batch_no = %(batch_no)s
                    """,
                    {"batch_no": result.batch_no},
                )
            cur.execute(
                """
                INSERT INTO t_import_log
                    (batch_no, import_user, file_name, total_rows, success_rows, fail_rows, duplicate_rows, status, remark)
                VALUES
                    (%(batch_no)s, %(user)s, %(file_name)s, %(total_rows)s, 0, %(fail_rows)s, 0, 'validated', %(remark)s)
                ON DUPLICATE KEY UPDATE
                    file_name = VALUES(file_name),
                    total_rows = VALUES(total_rows),
                    fail_rows = VALUES(fail_rows),
                    status = VALUES(status),
                    remark = VALUES(remark)
                """,
                {
                    "batch_no": result.batch_no,
                    "user": user["username"],
                    "file_name": filename,
                    "total_rows": result.total_rows,
                    "fail_rows": result.fail_rows,
                    "remark": result.error_summary,
                },
            )
            cur.execute(
                """
                UPDATE t_import_log l
                SET fail_rows = (
                    SELECT COUNT(*) FROM tmp_order_import t
                    WHERE t.batch_no = l.batch_no AND COALESCE(t.error_message, '') <> ''
                ),
                duplicate_rows = (
                    SELECT COUNT(*) FROM tmp_order_import t
                    WHERE t.batch_no = l.batch_no AND t.error_message LIKE '%%重复%%'
                )
                WHERE l.batch_no = %(batch_no)s
                """,
                {"batch_no": result.batch_no},
            )


@app.get("/imports/{batch_no}", response_class=HTMLResponse)
def import_detail(request: Request, batch_no: str):
    user = require_user(request, "import")
    if isinstance(user, RedirectResponse):
        return user
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM t_import_log WHERE batch_no = %(batch_no)s", {"batch_no": batch_no})
            log = cur.fetchone()
            if not log:
                raise HTTPException(status_code=404, detail="导入批次不存在")
            cur.execute(
                """
                SELECT *
                FROM tmp_order_import
                WHERE batch_no = %(batch_no)s
                ORDER BY COALESCE(error_message, '') <> '' DESC, row_no ASC
                LIMIT 200
                """,
                {"batch_no": batch_no},
            )
            rows = list(cur.fetchall())
    return render(request, "import_detail.html", {"user": user, "log": log, "rows": rows})


@app.post("/imports/{batch_no}/commit")
def import_commit(request: Request, batch_no: str):
    user = require_user(request, "import")
    if isinstance(user, RedirectResponse):
        return user
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM t_import_log WHERE batch_no = %(batch_no)s", {"batch_no": batch_no})
            log = cur.fetchone()
            if not log:
                raise HTTPException(status_code=404, detail="导入批次不存在")
            if log["status"] == "committed":
                return redirect(f"/imports/{batch_no}")
            cur.execute(
                "SELECT COUNT(*) AS c FROM tmp_order_import WHERE batch_no = %(batch_no)s AND COALESCE(error_message, '') <> ''",
                {"batch_no": batch_no},
            )
            if cur.fetchone()["c"]:
                raise HTTPException(status_code=400, detail="存在异常数据，不能确认入库")
            cur.execute(
                """
                INSERT INTO t_order_sku_detail (
                  link_id, sku_id, order_source, customer_no, customer_name, dept, platform, shop_name, order_no, original_order_no,
                  logistics_type, logistics_no, receiver_name, receiver_phone, category, product_name,
                  product_no, unit, qty, share_receivable, province, city, district, ship_time, cost, express_fee,
                  logistics_fee, freight, aux_material, share_cost
                )
                SELECT
                  link_id, sku_id, order_source, customer_no, customer_name, dept, platform, shop_name, order_no, original_order_no,
                  logistics_type, logistics_no, receiver_name, receiver_phone, category, product_name,
                  product_no, unit, qty, share_receivable, province, city, district, ship_time, cost, express_fee,
                  logistics_fee, freight, aux_material, share_cost
                FROM tmp_order_import
                WHERE batch_no = %(batch_no)s
                """,
                {"batch_no": batch_no},
            )
            success_rows = cur.rowcount
            cur.execute(
                """
                UPDATE t_import_log
                SET success_rows = %(success_rows)s, fail_rows = 0, status = 'committed', import_time = NOW()
                WHERE batch_no = %(batch_no)s
                """,
                {"success_rows": success_rows, "batch_no": batch_no},
            )
    return redirect(f"/imports/{batch_no}")


@app.get("/analytics/products", response_class=HTMLResponse)
def product_analytics(request: Request):
    user = require_user(request, "analytics")
    if isinstance(user, RedirectResponse):
        return user
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.product_no, o.product_name, o.category,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.cost) AS cost,
                       SUM(o.profit) AS profit,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.product_no, o.product_name, o.category
                ORDER BY revenue DESC
                LIMIT 100
                """,
                params,
            )
            rows = list(cur.fetchall())
            cur.execute(
                f"""
                SELECT o.category,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.cost) AS cost,
                       SUM(o.profit) AS profit,
                       COUNT(DISTINCT o.product_no) AS product_count,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.category
                ORDER BY revenue DESC
                LIMIT 30
                """,
                params,
            )
            category_rows = list(cur.fetchall())
    max_product_revenue = max([float(row["revenue"] or 0) for row in rows] or [0])
    max_category_revenue = max([float(row["revenue"] or 0) for row in category_rows] or [0])
    max_category_profit = max([abs(float(row["profit"] or 0)) for row in category_rows] or [0])
    for row in rows:
        revenue = float(row["revenue"] or 0)
        profit = float(row["profit"] or 0)
        row["revenue_pct"] = 0 if max_product_revenue == 0 else revenue / max_product_revenue * 100
        row["profit_pct"] = 0 if revenue == 0 else max(min(profit / revenue * 100, 100), -100)
    for row in category_rows:
        revenue = float(row["revenue"] or 0)
        profit = float(row["profit"] or 0)
        row["revenue_pct"] = 0 if max_category_revenue == 0 else revenue / max_category_revenue * 100
        row["profit_pct"] = 0 if max_category_profit == 0 else abs(profit) / max_category_profit * 100
        row["profit_width"] = row["profit_pct"]
        row["profit_negative"] = profit < 0
    return render(
        request,
        "analytics_products.html",
        {"user": user, "filters": filters, "rows": rows, "category_rows": category_rows},
    )


@app.get("/analytics/shops", response_class=HTMLResponse)
def shop_analytics(request: Request):
    user = require_user(request, "analytics")
    if isinstance(user, RedirectResponse):
        return user
    filters = default_filters(request)
    where, params = order_where(user, filters)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.platform, o.shop_name,
                       SUM(o.qty) AS qty,
                       SUM(o.share_receivable) AS revenue,
                       SUM(o.profit) AS profit,
                       CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate
                FROM t_order_sku_detail o
                {where}
                GROUP BY o.platform, o.shop_name
                ORDER BY revenue DESC
                LIMIT 100
                """,
                params,
            )
            rows = list(cur.fetchall())
    return render(request, "analytics_shops.html", {"user": user, "filters": filters, "rows": rows})


@app.get("/settings/users", response_class=HTMLResponse)
def settings_users(request: Request):
    user = require_user(request, "settings")
    if isinstance(user, RedirectResponse):
        return user
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.display_name, u.is_active,
                       GROUP_CONCAT(r.role_name ORDER BY r.id SEPARATOR ' / ') AS roles
                FROM t_user u
                LEFT JOIN t_user_role ur ON ur.user_id = u.id
                LEFT JOIN t_role r ON r.id = ur.role_id
                GROUP BY u.id, u.username, u.display_name, u.is_active
                ORDER BY u.id
                """
            )
            users = list(cur.fetchall())
    return render(request, "settings_users.html", {"user": user, "users": users})


@app.get("/settings/roles", response_class=HTMLResponse)
def settings_roles(request: Request):
    user = require_user(request, "settings")
    if isinstance(user, RedirectResponse):
        return user
    roles = load_roles_with_scopes()
    return render(request, "settings_roles.html", {"user": user, "roles": roles, "message": ""})


@app.post("/settings/roles", response_class=HTMLResponse)
def update_role_scope(
    request: Request,
    role_id: int = Form(...),
    dept_scope: str = Form("*"),
    platform_scope: str = Form("*"),
    shop_scope: str = Form("*"),
):
    user = require_user(request, "settings")
    if isinstance(user, RedirectResponse):
        return user
    scope_values = {
        "dept": split_scope(dept_scope),
        "platform": split_scope(platform_scope),
        "shop": split_scope(shop_scope),
    }
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM t_role_data_scope WHERE role_id = %(role_id)s", {"role_id": role_id})
            records = []
            for scope_type, values in scope_values.items():
                for value in values:
                    records.append({"role_id": role_id, "scope_type": scope_type, "scope_value": value})
            if records:
                cur.executemany(
                    """
                    INSERT INTO t_role_data_scope (role_id, scope_type, scope_value)
                    VALUES (%(role_id)s, %(scope_type)s, %(scope_value)s)
                    """,
                    records,
                )
    return render(request, "settings_roles.html", {"user": user, "roles": load_roles_with_scopes(), "message": "角色数据范围已保存"})


def split_scope(value: str) -> list[str]:
    cleaned = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    if not cleaned:
        return []
    if "*" in cleaned:
        return ["*"]
    return cleaned


def load_roles_with_scopes() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM t_role ORDER BY id")
            roles = list(cur.fetchall())
            cur.execute("SELECT role_id, scope_type, scope_value FROM t_role_data_scope ORDER BY scope_type, scope_value")
            rows = list(cur.fetchall())
    for role in roles:
        role["scopes"] = {"dept": [], "platform": [], "shop": []}
        for row in rows:
            if row["role_id"] == role["id"]:
                role["scopes"][row["scope_type"]].append(row["scope_value"])
        for key, values in role["scopes"].items():
            role["scopes"][key] = ",".join(values)
    return roles


@app.exception_handler(403)
def forbidden(request: Request, exc: HTTPException):
    user = current_user(request)
    return render(request, "error.html", {"user": user, "title": "没有权限", "message": exc.detail})
