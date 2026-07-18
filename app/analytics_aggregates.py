from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any, Iterable

from app.permissions import requested_scope_filters, scope_clause


PRODUCT_MONTHLY_TABLE = "agg_product_monthly"
DASHBOARD_MONTHLY_TABLE = "agg_dashboard_monthly"
DASHBOARD_DAILY_TABLE = "agg_dashboard_daily"
PLATFORM_MONTHLY_TABLE = "agg_platform_monthly"


def create_product_monthly_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PRODUCT_MONTHLY_TABLE} (
              stat_month DATE NOT NULL,
              dept VARCHAR(32) NOT NULL DEFAULT '',
              platform VARCHAR(32) NOT NULL DEFAULT '',
              shop_name VARCHAR(64) NOT NULL DEFAULT '',
              category VARCHAR(32) NOT NULL DEFAULT '',
              product_classification VARCHAR(64) NOT NULL DEFAULT '',
              product_no VARCHAR(64) NOT NULL DEFAULT '',
              product_name VARCHAR(255) NOT NULL DEFAULT '',
              qty DECIMAL(20,2) NOT NULL DEFAULT 0,
              revenue DECIMAL(20,2) NOT NULL DEFAULT 0,
              cost DECIMAL(20,2) NOT NULL DEFAULT 0,
              profit DECIMAL(20,2) NOT NULL DEFAULT 0,
              detail_rows BIGINT NOT NULL DEFAULT 0,
              order_count BIGINT NOT NULL DEFAULT 0,
              latest_ship_time DATETIME NULL,
              refreshed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (
                stat_month, dept, platform, shop_name, category,
                product_classification, product_no
              ),
              KEY idx_agg_product_month_product (stat_month, product_no),
              KEY idx_agg_product_month_shop (stat_month, platform, shop_name),
              KEY idx_agg_product_month_category (
                stat_month, category, product_classification
              )
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='monthly product analytics aggregate'
            """
        )


def create_dashboard_tables(conn) -> None:
    with conn.cursor() as cur:
        for table, date_column in (
            (DASHBOARD_MONTHLY_TABLE, "stat_month"),
            (DASHBOARD_DAILY_TABLE, "stat_date"),
        ):
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                  {date_column} DATE NOT NULL,
                  revenue DECIMAL(20,2) NOT NULL DEFAULT 0,
                  qty DECIMAL(20,2) NOT NULL DEFAULT 0,
                  profit DECIMAL(20,2) NOT NULL DEFAULT 0,
                  orders BIGINT NOT NULL DEFAULT 0,
                  customers BIGINT NOT NULL DEFAULT 0,
                  products BIGINT NOT NULL DEFAULT 0,
                  loss_orders BIGINT NOT NULL DEFAULT 0,
                  detail_rows BIGINT NOT NULL DEFAULT 0,
                  latest_ship_time DATETIME NULL,
                  refreshed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY ({date_column})
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='precomputed global dashboard metrics'
                """
            )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PLATFORM_MONTHLY_TABLE} (
              stat_month DATE NOT NULL,
              platform VARCHAR(32) NOT NULL DEFAULT '',
              revenue DECIMAL(20,2) NOT NULL DEFAULT 0,
              qty DECIMAL(20,2) NOT NULL DEFAULT 0,
              profit DECIMAL(20,2) NOT NULL DEFAULT 0,
              orders BIGINT NOT NULL DEFAULT 0,
              detail_rows BIGINT NOT NULL DEFAULT 0,
              refreshed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (stat_month, platform)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            COMMENT='precomputed monthly platform metrics'
            """
        )


def normalize_month(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date().replace(day=1)


def next_month(value: date) -> date:
    return date(value.year + (1 if value.month == 12 else 0), 1 if value.month == 12 else value.month + 1, 1)


def refresh_product_months(conn, months: Iterable[date | datetime | str]) -> list[date]:
    normalized = sorted({normalize_month(month) for month in months})
    if not normalized:
        return []
    with conn.cursor() as cur:
        for month in normalized:
            month_end = next_month(month)
            params = {"month": month.isoformat(), "month_end": month_end.isoformat()}
            cur.execute(
                f"DELETE FROM {PRODUCT_MONTHLY_TABLE} WHERE stat_month = %(month)s",
                params,
            )
            cur.execute(
                f"""
                INSERT INTO {PRODUCT_MONTHLY_TABLE} (
                  stat_month, dept, platform, shop_name, category,
                  product_classification, product_no, product_name,
                  qty, revenue, cost, profit, detail_rows, order_count,
                  latest_ship_time, refreshed_at
                )
                SELECT
                  %(month)s,
                  o.dept,
                  o.platform,
                  o.shop_name,
                  o.category,
                  o.product_classification,
                  o.product_no,
                  MAX(o.product_name),
                  COALESCE(SUM(o.qty), 0),
                  COALESCE(SUM(o.share_receivable), 0),
                  COALESCE(SUM(o.cost), 0),
                  COALESCE(SUM(o.profit), 0),
                  COUNT(*),
                  COUNT(DISTINCT o.order_no),
                  MAX(o.ship_time),
                  NOW()
                FROM t_order_sku_detail o
                WHERE o.ship_time >= %(month)s
                  AND o.ship_time < %(month_end)s
                GROUP BY
                  o.dept, o.platform, o.shop_name, o.category,
                  o.product_classification, o.product_no
                """,
                params,
            )
    return normalized


def refresh_dashboard_months(conn, months: Iterable[date | datetime | str]) -> list[date]:
    normalized = sorted({normalize_month(month) for month in months})
    if not normalized:
        return []
    with conn.cursor() as cur:
        for month in normalized:
            month_end = next_month(month)
            params = {"month": month.isoformat(), "month_end": month_end.isoformat()}
            cur.execute(
                f"DELETE FROM {DASHBOARD_MONTHLY_TABLE} WHERE stat_month = %(month)s",
                params,
            )
            cur.execute(
                f"""
                INSERT INTO {DASHBOARD_MONTHLY_TABLE} (
                  stat_month, revenue, qty, profit, orders, customers,
                  products, loss_orders, detail_rows, latest_ship_time,
                  refreshed_at
                )
                SELECT
                  %(month)s,
                  COALESCE(SUM(o.share_receivable), 0),
                  COALESCE(SUM(o.qty), 0),
                  COALESCE(SUM(o.profit), 0),
                  COUNT(DISTINCT o.order_no),
                  COUNT(DISTINCT o.customer_no),
                  COUNT(DISTINCT o.product_no),
                  COUNT(DISTINCT CASE WHEN o.profit < 0 THEN o.order_no END),
                  COUNT(*),
                  MAX(o.ship_time),
                  NOW()
                FROM t_order_sku_detail o
                WHERE o.ship_time >= %(month)s
                  AND o.ship_time < %(month_end)s
                """,
                params,
            )

            cur.execute(
                f"DELETE FROM {DASHBOARD_DAILY_TABLE} WHERE stat_date >= %(month)s AND stat_date < %(month_end)s",
                params,
            )
            cur.execute(
                f"""
                INSERT INTO {DASHBOARD_DAILY_TABLE} (
                  stat_date, revenue, qty, profit, orders, customers,
                  products, loss_orders, detail_rows, latest_ship_time,
                  refreshed_at
                )
                SELECT
                  DATE(o.ship_time),
                  COALESCE(SUM(o.share_receivable), 0),
                  COALESCE(SUM(o.qty), 0),
                  COALESCE(SUM(o.profit), 0),
                  COUNT(DISTINCT o.order_no),
                  COUNT(DISTINCT o.customer_no),
                  COUNT(DISTINCT o.product_no),
                  COUNT(DISTINCT CASE WHEN o.profit < 0 THEN o.order_no END),
                  COUNT(*),
                  MAX(o.ship_time),
                  NOW()
                FROM t_order_sku_detail o
                WHERE o.ship_time >= %(month)s
                  AND o.ship_time < %(month_end)s
                GROUP BY DATE(o.ship_time)
                """,
                params,
            )

            cur.execute(
                f"DELETE FROM {PLATFORM_MONTHLY_TABLE} WHERE stat_month = %(month)s",
                params,
            )
            cur.execute(
                f"""
                INSERT INTO {PLATFORM_MONTHLY_TABLE} (
                  stat_month, platform, revenue, qty, profit, orders,
                  detail_rows, refreshed_at
                )
                SELECT
                  %(month)s,
                  o.platform,
                  COALESCE(SUM(o.share_receivable), 0),
                  COALESCE(SUM(o.qty), 0),
                  COALESCE(SUM(o.profit), 0),
                  COUNT(DISTINCT o.order_no),
                  COUNT(*),
                  NOW()
                FROM t_order_sku_detail o
                WHERE o.ship_time >= %(month)s
                  AND o.ship_time < %(month_end)s
                GROUP BY o.platform
                """,
                params,
            )
    return normalized


def full_calendar_month_range(filters: dict[str, Any]) -> tuple[date, date] | None:
    try:
        start = datetime.strptime(str(filters["start_time"]), "%Y-%m-%d").date()
        end = datetime.strptime(str(filters["end_time"]), "%Y-%m-%d").date()
    except (KeyError, TypeError, ValueError):
        return None
    if start.day != 1 or end.day != monthrange(end.year, end.month)[1]:
        return None
    return start, end.replace(day=1)


def can_use_product_monthly(filters: dict[str, Any]) -> bool:
    return full_calendar_month_range(filters) is not None and not filters.get("order_no")


def can_use_global_monthly(user: dict[str, Any], filters: dict[str, Any]) -> bool:
    month_range = full_calendar_month_range(filters)
    if month_range is None or month_range[0] != month_range[1]:
        return False
    if not all(user.get("all_scopes", {}).get(key) for key in ("dept", "platform", "shop")):
        return False
    return not any(
        filters.get(key)
        for key in (
            "dept",
            "platform",
            "shop_name",
            "category",
            "product_classification",
            "product",
            "order_no",
        )
    )


def product_monthly_where(
    user: dict[str, Any],
    filters: dict[str, Any],
    alias: str = "a",
) -> tuple[str, dict[str, Any]]:
    month_range = full_calendar_month_range(filters)
    if month_range is None:
        raise ValueError("product monthly aggregate requires complete calendar months")
    start_month, end_month = month_range
    params = dict(filters)
    params.update(
        {
            "start_month": start_month.isoformat(),
            "end_month": end_month.isoformat(),
        }
    )
    clauses = [
        f"{alias}.stat_month >= %(start_month)s",
        f"{alias}.stat_month <= %(end_month)s",
    ]
    if filters.get("category"):
        clauses.append(f"{alias}.category = %(category)s")
    if filters.get("product_classification"):
        clauses.append(f"{alias}.product_classification = %(product_classification)s")
    if filters.get("product"):
        clauses.append(
            f"({alias}.product_name LIKE %(product_like)s "
            f"OR {alias}.product_no LIKE %(product_like)s)"
        )
        params["product_like"] = f"%{filters['product']}%"
    scope_filter, params = requested_scope_filters(params, alias)
    where = " WHERE " + " AND ".join(clauses) + scope_filter + scope_clause(user, params, alias, "agg_scope")
    return where, params
