from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    select_sql: str
    group_sql: str


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    select_sql: str


DIMENSIONS: dict[str, Dimension] = {
    "month": Dimension("month", "月份", "DATE_FORMAT(o.ship_time, '%%Y-%%m') AS month", "DATE_FORMAT(o.ship_time, '%%Y-%%m')"),
    "category": Dimension("category", "产品大类", "o.category AS category", "o.category"),
    "product": Dimension(
        "product",
        "产品",
        "o.product_no AS product_no, o.product_name AS product_name",
        "o.product_no, o.product_name",
    ),
    "platform": Dimension("platform", "平台", "o.platform AS platform", "o.platform"),
    "shop": Dimension("shop", "店铺", "o.shop_name AS shop_name", "o.shop_name"),
    "dept": Dimension("dept", "部门", "o.dept AS dept", "o.dept"),
    "customer": Dimension(
        "customer",
        "客户",
        "o.customer_no AS customer_no, o.customer_name AS customer_name",
        "o.customer_no, o.customer_name",
    ),
    "province": Dimension("province", "省份", "o.province AS province", "o.province"),
    "city": Dimension("city", "城市", "o.city AS city", "o.city"),
    "order_source": Dimension("order_source", "订单来源", "o.order_source AS order_source", "o.order_source"),
}


METRICS: dict[str, Metric] = {
    "revenue": Metric("revenue", "销售额", "COALESCE(SUM(o.share_receivable), 0) AS revenue"),
    "qty": Metric("qty", "销量", "COALESCE(SUM(o.qty), 0) AS qty"),
    "profit": Metric("profit", "利润", "COALESCE(SUM(o.profit), 0) AS profit"),
    "cost": Metric("cost", "成本", "COALESCE(SUM(o.cost), 0) AS cost"),
    "orders": Metric("orders", "订单数", "COUNT(DISTINCT o.order_no) AS orders"),
    "profit_rate": Metric(
        "profit_rate",
        "利润率",
        "CASE WHEN SUM(o.share_receivable) = 0 THEN 0 ELSE SUM(o.profit) / SUM(o.share_receivable) * 100 END AS profit_rate",
    ),
}

DEFAULT_METRICS = ["revenue", "qty", "profit", "profit_rate", "orders"]
FILTER_KEYS = ("start_time", "end_time", "dept", "platform", "shop_name", "category", "product", "order_no")
FORBIDDEN_SQL_TOKENS = (
    " insert ",
    " update ",
    " delete ",
    " drop ",
    " alter ",
    " truncate ",
    " create ",
    " replace ",
    " grant ",
    " revoke ",
    " call ",
)


def default_analysis_filters(today: date | None = None) -> dict[str, Any]:
    current = today or date.today()
    return {
        "start_time": date(current.year, 1, 1).isoformat(),
        "end_time": current.isoformat(),
        "dept": "",
        "platform": "",
        "shop_name": "",
        "category": "",
        "product": "",
        "order_no": "",
    }


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def parse_question_filters(question: str, today: date | None = None) -> dict[str, Any]:
    filters = default_analysis_filters(today)
    current = today or date.today()
    text = normalize_question(question)

    year = current.year
    year_match = re.search(r"(20\d{2})年", text)
    if year_match:
        year = int(year_match.group(1))
    elif "去年" in text:
        year = current.year - 1

    month_range = re.search(r"(\d{1,2})\s*(?:-|~|—|至|到)\s*(\d{1,2})月", text)
    if month_range:
        start_month = clamp_month(int(month_range.group(1)))
        end_month = clamp_month(int(month_range.group(2)))
        if start_month > end_month:
            start_month, end_month = end_month, start_month
        filters["start_time"] = date(year, start_month, 1).isoformat()
        filters["end_time"] = month_end(year, end_month).isoformat()
        return filters

    single_month = re.search(r"(?<!\d)(\d{1,2})月", text)
    if single_month:
        month = clamp_month(int(single_month.group(1)))
        filters["start_time"] = date(year, month, 1).isoformat()
        filters["end_time"] = month_end(year, month).isoformat()
        return filters

    if "上半年" in text:
        filters["start_time"] = date(year, 1, 1).isoformat()
        filters["end_time"] = date(year, 6, 30).isoformat()
    elif "下半年" in text:
        filters["start_time"] = date(year, 7, 1).isoformat()
        filters["end_time"] = date(year, 12, 31).isoformat()
    elif "本月" in text or "这个月" in text:
        filters["start_time"] = date(current.year, current.month, 1).isoformat()
        filters["end_time"] = current.isoformat()
    elif "上月" in text or "上个月" in text:
        first_this_month = date(current.year, current.month, 1)
        last_prev_month = first_this_month - timedelta(days=1)
        filters["start_time"] = date(last_prev_month.year, last_prev_month.month, 1).isoformat()
        filters["end_time"] = last_prev_month.isoformat()
    elif "近7天" in text or "最近7天" in text:
        filters["start_time"] = (current - timedelta(days=6)).isoformat()
        filters["end_time"] = current.isoformat()
    elif "近30天" in text or "最近30天" in text:
        filters["start_time"] = (current - timedelta(days=29)).isoformat()
        filters["end_time"] = current.isoformat()
    elif "全年" in text or "今年" in text:
        filters["start_time"] = date(year, 1, 1).isoformat()
        filters["end_time"] = date(year, 12, 31).isoformat() if year != current.year else current.isoformat()

    return filters


def clamp_month(value: int) -> int:
    return max(1, min(12, value))


def month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def detect_dimensions(question: str) -> list[str]:
    text = normalize_question(question)
    dimensions: list[str] = []
    if any(word in text for word in ("趋势", "按月", "每月", "月度", "月份")):
        dimensions.append("month")
    if any(word in text for word in ("大类", "品类", "分类", "类目")):
        dimensions.append("category")
    if any(word in text for word in ("产品", "商品", "货品", "货号", "sku")):
        dimensions.append("product")
    if any(word in text for word in ("平台", "渠道")):
        dimensions.append("platform")
    if any(word in text for word in ("店铺", "门店", "店")):
        dimensions.append("shop")
    if "部门" in text:
        dimensions.append("dept")
    if "客户" in text:
        dimensions.append("customer")
    if any(word in text for word in ("省份", "省", "地区")):
        dimensions.append("province")
    if "城市" in text or "市" in text:
        dimensions.append("city")
    if any(word in text for word in ("来源", "订单来源")):
        dimensions.append("order_source")

    unique_dimensions = []
    for key in dimensions:
        if key not in unique_dimensions:
            unique_dimensions.append(key)
    return unique_dimensions[:3] or ["product"]


def detect_metrics(question: str) -> tuple[list[str], str, bool]:
    text = normalize_question(question)
    metrics: list[str] = []
    if any(word in text for word in ("销售额", "应收", "收入", "金额", "gmv", "占比")):
        metrics.append("revenue")
    if any(word in text for word in ("销量", "数量", "件数")):
        metrics.append("qty")
    if "利润率" in text or "毛利率" in text:
        metrics.append("profit_rate")
    if "利润" in text or "毛利" in text:
        metrics.append("profit")
    if "成本" in text:
        metrics.append("cost")
    if any(word in text for word in ("订单数", "单量", "订单量")):
        metrics.append("orders")

    unique_metrics = []
    for key in metrics or DEFAULT_METRICS:
        if key not in unique_metrics:
            unique_metrics.append(key)

    if "利润" in text:
        order_metric = "profit"
    elif any(word in text for word in ("销量", "数量", "件数")):
        order_metric = "qty"
    elif any(word in text for word in ("订单数", "单量", "订单量")):
        order_metric = "orders"
    elif "成本" in text:
        order_metric = "cost"
    else:
        order_metric = "revenue"

    wants_share = any(word in text for word in ("占比", "占", "比例", "结构", "份额"))
    if wants_share and "revenue" not in unique_metrics:
        unique_metrics.insert(0, "revenue")
    return unique_metrics[:5], order_metric, wants_share


def normalize_analysis_intent(intent: dict[str, Any]) -> dict[str, Any] | None:
    raw_dimensions = intent.get("dimensions")
    raw_metrics = intent.get("metrics")
    if not isinstance(raw_dimensions, list) or not isinstance(raw_metrics, list):
        return None

    dimensions = unique_allowed(raw_dimensions, DIMENSIONS, 3)
    metrics = unique_allowed(raw_metrics, METRICS, 5)
    order_metric = intent.get("order_metric")
    if not isinstance(order_metric, str) or order_metric not in METRICS:
        order_metric = metrics[0] if metrics else "revenue"
    wants_share = intent.get("wants_share") is True
    if wants_share and "revenue" not in metrics:
        metrics.insert(0, "revenue")
    if not dimensions or not metrics:
        return None
    return {
        "dimensions": dimensions,
        "metrics": metrics,
        "order_metric": order_metric,
        "wants_share": wants_share,
    }


def unique_allowed(values: list[Any], allowed: dict[str, Any], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value in allowed and value not in result:
            result.append(value)
        if len(result) == limit:
            break
    return result


def build_sql(question: str, where: str, params: dict[str, Any], intent: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_intent = normalize_analysis_intent(intent) if intent else None
    if normalized_intent:
        dimensions = normalized_intent["dimensions"]
        metrics = normalized_intent["metrics"]
        order_metric = normalized_intent["order_metric"]
        wants_share = normalized_intent["wants_share"]
    else:
        dimensions = detect_dimensions(question)
        metrics, order_metric, wants_share = detect_metrics(question)
    if order_metric not in metrics and order_metric in METRICS:
        metrics.insert(0, order_metric)

    select_parts = [DIMENSIONS[key].select_sql for key in dimensions]
    select_parts.extend(METRICS[key].select_sql for key in metrics)
    if wants_share:
        select_parts.append(
            "CASE WHEN totals.total_revenue = 0 THEN 0 "
            "ELSE SUM(o.share_receivable) / totals.total_revenue * 100 END AS revenue_share_pct"
        )

    group_parts = []
    for key in dimensions:
        group_parts.extend(part.strip() for part in DIMENSIONS[key].group_sql.split(","))
    group_by = ", ".join(group_parts)
    order_by = "month ASC" if dimensions == ["month"] else f"{order_metric} DESC"
    limit = 120 if len(dimensions) > 1 else 60

    joins = ""
    if wants_share:
        joins = f"""
                CROSS JOIN (
                  SELECT COALESCE(SUM(o.share_receivable), 0) AS total_revenue
                  FROM t_order_sku_detail o
                  {where}
                ) totals
        """

    sql = f"""
                SELECT
                  {", ".join(select_parts)}
                FROM t_order_sku_detail o
                {joins}
                {where}
                GROUP BY {group_by}
                ORDER BY {order_by}
                LIMIT {limit}
                """
    return {
        "sql": normalize_sql(sql),
        "params": dict(params),
        "dimensions": dimensions,
        "metrics": metrics,
        "order_metric": order_metric,
        "wants_share": wants_share,
    }


def build_chart(question: str, rows: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    dimensions = plan["dimensions"]
    metric = "revenue_share_pct" if plan["wants_share"] else plan["order_metric"]
    metric_label = "销售额占比" if metric == "revenue_share_pct" else METRICS.get(metric, METRICS["revenue"]).label
    chart_type = "line" if dimensions == ["month"] else "pie" if plan["wants_share"] and len(dimensions) == 1 else "bar"
    points = []
    for row in rows[:30]:
        value = to_float(row.get(metric))
        points.append(
            {
                "label": row_label(row, dimensions),
                "value": value,
                "display": f"{value:.2f}%" if metric == "revenue_share_pct" else value,
            }
        )
    return {
        "type": chart_type,
        "metric": metric,
        "metric_label": metric_label,
        "points": points,
    }


def row_label(row: dict[str, Any], dimensions: list[str]) -> str:
    labels: list[str] = []
    for key in dimensions:
        if key == "product":
            labels.append(str(row.get("product_name") or row.get("product_no") or "未命名产品"))
        elif key == "customer":
            labels.append(str(row.get("customer_name") or row.get("customer_no") or "未命名客户"))
        elif key == "shop":
            labels.append(str(row.get("shop_name") or "未命名店铺"))
        else:
            labels.append(str(row.get(key) or "未分类"))
    return " / ".join(labels)


def summarize_answer(question: str, rows: list[dict[str, Any]], plan: dict[str, Any]) -> str:
    if not rows:
        return "当前条件下没有查询到数据。"
    metric = "revenue_share_pct" if plan["wants_share"] else plan["order_metric"]
    top = rows[0]
    top_label = row_label(top, plan["dimensions"])
    top_value = to_float(top.get(metric))
    suffix = "%" if metric == "revenue_share_pct" else ""
    return f"按当前口径查询，排名第一的是 {top_label}，{chart_metric_name(metric)} 为 {top_value:.2f}{suffix}。"


def chart_metric_name(metric: str) -> str:
    if metric == "revenue_share_pct":
        return "销售额占比"
    return METRICS.get(metric, METRICS["revenue"]).label


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        item = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                item[key] = float(value)
            elif hasattr(value, "isoformat"):
                item[key] = value.isoformat()
            else:
                item[key] = value
        normalized.append(item)
    return normalized


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_sql(sql: str) -> str:
    return "\n".join(line.rstrip() for line in sql.strip().splitlines())


def audit_sql_plan(sql: str, params: dict[str, Any]) -> None:
    normalized = re.sub(r"\s+", " ", sql).strip().lower()
    compact = f" {normalized} "
    if not compact.strip().startswith("select "):
        raise ValueError("analytics SQL must be a SELECT")
    if ";" in compact or "--" in compact or "/*" in compact or "*/" in compact:
        raise ValueError("analytics SQL must be a single statement without comments")
    if " from t_order_sku_detail o " not in compact:
        raise ValueError("analytics SQL must read from t_order_sku_detail")
    if any(token in compact for token in FORBIDDEN_SQL_TOKENS):
        raise ValueError("analytics SQL contains a forbidden statement")
    if "%(start_time)s" not in sql or "%(end_time_exclusive)s" not in sql:
        raise ValueError("analytics SQL must include a ship_time range")
    if "start_time" not in params or "end_time_exclusive" not in params:
        raise ValueError("analytics SQL is missing time parameters")
    limit_match = re.search(r"\blimit\s+(\d+)\s*$", compact)
    if not limit_match or int(limit_match.group(1)) > 200:
        raise ValueError("analytics SQL must end with LIMIT <= 200")
