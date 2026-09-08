from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
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
    "product_classification": Dimension(
        "product_classification",
        "货品分类",
        "o.product_classification AS product_classification",
        "o.product_classification",
    ),
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
FILTER_KEYS = (
    "start_time",
    "end_time",
    "dept",
    "platform",
    "shop_name",
    "category",
    "product_classification",
    "product",
    "order_no",
    "province",
    "city",
    "order_source",
)
ENTITY_FILTER_KEYS = (
    "dept",
    "platform",
    "shop_name",
    "category",
    "product_classification",
    "product",
    "province",
    "city",
    "order_source",
)
FILTER_LABELS = {
    "dept": "部门",
    "platform": "平台",
    "shop_name": "店铺",
    "category": "产品大类",
    "product_classification": "货品分类",
    "product": "产品",
    "order_no": "订单号",
    "province": "省份",
    "city": "城市",
    "order_source": "订单来源",
}
ANALYSIS_TYPES = {"ranking", "trend", "share", "comparison", "contribution", "diagnosis"}
COMPARISON_MODES = {"none", "previous_period", "year_over_year"}
SORT_DIRECTIONS = {"asc", "desc"}
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
        "product_classification": "",
        "product": "",
        "order_no": "",
        "province": "",
        "city": "",
        "order_source": "",
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
    elif "去年" in text and "今年" not in text:
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

    quarter_match = re.search(r"(?:第)?([一二三四1234])季度|q([1-4])", text)
    if quarter_match:
        raw_quarter = quarter_match.group(1) or quarter_match.group(2)
        quarter = {"一": 1, "二": 2, "三": 3, "四": 4}.get(raw_quarter)
        if quarter is None:
            quarter = int(raw_quarter)
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        filters["start_time"] = date(year, start_month, 1).isoformat()
        filters["end_time"] = month_end(year, end_month).isoformat()
    elif "本季度" in text or "这个季度" in text:
        start_month = ((current.month - 1) // 3) * 3 + 1
        filters["start_time"] = date(current.year, start_month, 1).isoformat()
        filters["end_time"] = current.isoformat()
    elif "上季度" in text or "上个季度" in text:
        current_quarter_start = date(current.year, ((current.month - 1) // 3) * 3 + 1, 1)
        previous_quarter_end = current_quarter_start - timedelta(days=1)
        previous_quarter_start_month = ((previous_quarter_end.month - 1) // 3) * 3 + 1
        filters["start_time"] = date(previous_quarter_end.year, previous_quarter_start_month, 1).isoformat()
        filters["end_time"] = previous_quarter_end.isoformat()
    elif re.search(r"(?:近|最近)\d{1,2}个月", text):
        months = min(36, max(1, int(re.search(r"(?:近|最近)(\d{1,2})个月", text).group(1))))
        start_month = add_months(date(current.year, current.month, 1), -(months - 1))
        filters["start_time"] = start_month.isoformat()
        filters["end_time"] = current.isoformat()
    elif "上半年" in text:
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


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def shift_year(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def comparison_range(start_time: str, end_time: str, mode: str) -> dict[str, str] | None:
    if mode not in COMPARISON_MODES or mode == "none":
        return None
    start = date.fromisoformat(start_time)
    end = date.fromisoformat(end_time)
    if mode == "year_over_year":
        compare_start = shift_year(start, -1)
        compare_end = shift_year(end, -1)
        label = "去年同期"
    else:
        span = end - start
        compare_end = start - timedelta(days=1)
        compare_start = compare_end - span
        label = "前一周期"
    return {
        "mode": mode,
        "label": label,
        "start_time": compare_start.isoformat(),
        "end_time": compare_end.isoformat(),
    }


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
    if "货品分类" in text:
        dimensions.append("product_classification")
    if "货品分类" not in text and any(word in text for word in ("大类", "品类", "分类", "类目")):
        dimensions.append("category")
    if "货品分类" not in text and any(word in text for word in ("产品", "商品", "货品", "货号", "sku")):
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
    if ("利润" in text or "毛利" in text) and "利润率" not in text and "毛利率" not in text:
        metrics.append("profit")
    if "成本" in text:
        metrics.append("cost")
    if any(word in text for word in ("订单数", "单量", "订单量")):
        metrics.append("orders")

    unique_metrics = []
    for key in metrics or DEFAULT_METRICS:
        if key not in unique_metrics:
            unique_metrics.append(key)

    if "利润率" in text or "毛利率" in text:
        order_metric = "profit_rate"
    elif "利润" in text or "毛利" in text:
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


def detect_analysis_type(question: str, wants_share: bool = False) -> str:
    text = normalize_question(question)
    if any(word in text for word in ("为什么", "原因", "建议", "怎么改善", "怎么提升", "异常", "拖累", "风险")):
        return "diagnosis"
    if any(word in text for word in ("贡献", "造成", "带来增长", "影响最大", "拉动")):
        return "contribution"
    if any(word in text for word in ("同比", "环比", "较去年", "比去年", "相比", "增长", "下降", "变化")):
        return "comparison"
    if any(word in text for word in ("趋势", "走势", "按月", "每月", "月度")):
        return "trend"
    if wants_share:
        return "share"
    return "ranking"


def detect_comparison_mode(question: str) -> str:
    text = normalize_question(question)
    if any(word in text for word in ("同比", "去年同期", "较去年", "比去年")):
        return "year_over_year"
    if any(word in text for word in ("环比", "前一周期", "上期", "相比")):
        return "previous_period"
    return "none"


def detect_sort_direction(question: str) -> str:
    text = normalize_question(question)
    if any(word in text for word in ("最低", "最差", "倒数", "下滑", "拖累", "亏损", "bottom")):
        return "asc"
    return "desc"


def detect_limit(question: str) -> int:
    text = normalize_question(question)
    match = re.search(r"(?:top|前|排名前|倒数)(\d{1,3})", text)
    if not match:
        return 10
    return max(1, min(50, int(match.group(1))))


def has_explicit_limit(question: str) -> bool:
    return bool(re.search(r"(?:top|前|排名前|倒数)\d{1,3}", normalize_question(question)))


def explicit_question_signals(question: str) -> dict[str, bool]:
    text = normalize_question(question)
    return {
        "time": bool(
            re.search(r"20\d{2}年|\d{1,2}月|季度|半年|今年|去年|本月|上月|近\d+[天个]", text)
        ),
        "metric": any(
            word in text
            for word in ("销售额", "收入", "金额", "销量", "数量", "利润", "毛利", "成本", "订单", "单量")
        ),
        "dimension": any(
            word in text
            for word in (
                "产品",
                "商品",
                "货品",
                "分类",
                "类目",
                "平台",
                "渠道",
                "店铺",
                "部门",
                "客户",
                "地区",
                "省",
                "城市",
                "来源",
                "趋势",
                "按月",
            )
        ),
    }


def rule_filter_hints(question: str) -> dict[str, str]:
    text = question.strip()
    hints: dict[str, str] = {}
    patterns = (
        ("platform", r"(?:在|看|分析|筛选)?([\u4e00-\u9fffA-Za-z0-9_-]{1,16})(?:平台|渠道)"),
        ("shop_name", r"(?:在|看|分析|筛选)?([\u4e00-\u9fffA-Za-z0-9_-]{1,20})(?:店铺|门店)"),
        ("dept", r"(?:在|看|分析|筛选)?([\u4e00-\u9fffA-Za-z0-9_-]{1,16})(?:部门|大区|区域)"),
        ("category", r"(?:在|看|分析|筛选)?([\u4e00-\u9fffA-Za-z0-9_-]{1,16})(?:类目|品类|大类)"),
        ("product_classification", r"(?:在|看|分析|筛选)?([\u4e00-\u9fffA-Za-z0-9_-]{1,20})货品分类"),
        ("province", r"(?:在|看|分析|筛选)?([\u4e00-\u9fff]{2,8})(?:省|地区)"),
        ("city", r"(?:在|看|分析|筛选)?([\u4e00-\u9fff]{2,8})市"),
        ("order_source", r"(?:来自|来源于|订单来源为)([\u4e00-\u9fffA-Za-z0-9_-]{1,20})"),
    )
    stop_prefixes = ("今年", "去年", "本月", "上月", "各", "每个", "所有", "一下", "一下在", "看看", "查看", "帮我")
    for field, pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip("的 ：:")
        for prefix in stop_prefixes:
            if value.startswith(prefix) and len(value) > len(prefix):
                value = value[len(prefix) :]
        if value and value not in ("各", "每个", "所有", "销售", "订单", "分析", "数据"):
            hints[field] = value
    region_match = re.search(r"(华东|华南|华北|华中|东北|西北|西南)(?:地区|区域|大区)", text)
    if region_match:
        hints["dept"] = region_match.group(1)
    return hints


def build_rule_intent(question: str, today: date | None = None) -> dict[str, Any]:
    current = today or date.today()
    filters = parse_question_filters(question, today=current)
    dimensions = detect_dimensions(question)
    metrics, order_metric, wants_share = detect_metrics(question)
    analysis_type = detect_analysis_type(question, wants_share)
    comparison_mode = detect_comparison_mode(question)
    if analysis_type == "comparison" and comparison_mode == "none":
        comparison_mode = "previous_period"
    comparison = comparison_range(filters["start_time"], filters["end_time"], comparison_mode)
    signals = explicit_question_signals(question)
    confidence = 0.58 + sum(0.09 for present in signals.values() if present)
    assumptions: list[str] = []
    if not signals["time"]:
        assumptions.append("未识别到明确时间，默认使用今年至今")
    if not signals["metric"]:
        assumptions.append("未识别到明确指标，默认展示销售额、销量、利润、利润率和订单数")
    if not signals["dimension"]:
        assumptions.append("未识别到明确维度，默认按产品分析")
    return {
        "version": "2",
        "analysis_type": analysis_type,
        "time_range": {
            "start_time": filters["start_time"],
            "end_time": filters["end_time"],
            "label": time_range_label(question, filters),
        },
        "comparison": comparison or {"mode": "none", "label": "不对比"},
        "filters": {key: "" for key in FILTER_KEYS if key not in ("start_time", "end_time")},
        "filter_hints": rule_filter_hints(question),
        "dimensions": dimensions,
        "metrics": metrics,
        "order_metric": order_metric,
        "wants_share": wants_share,
        "sort_direction": detect_sort_direction(question),
        "limit": 36 if analysis_type == "trend" and not has_explicit_limit(question) else detect_limit(question),
        "confidence": min(0.9, confidence),
        "assumptions": assumptions,
        "clarifications": [],
        "narrative_goal": question[:200],
    }


def time_range_label(question: str, filters: dict[str, Any]) -> str:
    text = normalize_question(question)
    for label in (
        "今年上半年",
        "去年上半年",
        "今年下半年",
        "去年下半年",
        "本季度",
        "上季度",
        "本月",
        "上月",
        "今年",
        "去年",
    ):
        if label in text:
            return label
    return f"{filters['start_time']} 至 {filters['end_time']}"


def normalize_analysis_intent_v2(
    intent: dict[str, Any],
    question: str,
    today: date | None = None,
) -> dict[str, Any] | None:
    if not isinstance(intent, dict):
        return None
    fallback = build_rule_intent(question, today=today)

    dimensions = unique_allowed(intent.get("dimensions") or fallback["dimensions"], DIMENSIONS, 3)
    metrics = unique_allowed(intent.get("metrics") or fallback["metrics"], METRICS, 5)
    if not dimensions or not metrics:
        return None

    analysis_type = intent.get("analysis_type")
    if analysis_type not in ANALYSIS_TYPES:
        analysis_type = fallback["analysis_type"]

    raw_time_range = intent.get("time_range")
    time_range = dict(fallback["time_range"])
    if isinstance(raw_time_range, dict):
        start_time = valid_iso_date(raw_time_range.get("start_time"))
        end_time = valid_iso_date(raw_time_range.get("end_time"))
        if start_time and end_time and start_time <= end_time:
            time_range["start_time"] = start_time
            time_range["end_time"] = end_time
            label = raw_time_range.get("label")
            if isinstance(label, str) and label.strip():
                time_range["label"] = label.strip()[:60]

    raw_comparison = intent.get("comparison")
    comparison_mode = "none"
    if isinstance(raw_comparison, dict) and raw_comparison.get("mode") in COMPARISON_MODES:
        comparison_mode = raw_comparison["mode"]
    elif isinstance(raw_comparison, str) and raw_comparison in COMPARISON_MODES:
        comparison_mode = raw_comparison
    elif fallback["comparison"]["mode"] in COMPARISON_MODES:
        comparison_mode = fallback["comparison"]["mode"]
    comparison = comparison_range(time_range["start_time"], time_range["end_time"], comparison_mode)

    raw_filters = intent.get("filters")
    normalized_filters = {key: "" for key in FILTER_KEYS if key not in ("start_time", "end_time")}
    if isinstance(raw_filters, dict):
        for key in normalized_filters:
            value = raw_filters.get(key)
            if isinstance(value, (str, int, float)) and str(value).strip():
                normalized_filters[key] = str(value).strip()[:128]

    raw_hints = intent.get("filter_hints")
    filter_hints = dict(fallback["filter_hints"])
    if isinstance(raw_hints, dict):
        for key in ENTITY_FILTER_KEYS:
            if key not in raw_hints:
                continue
            value = raw_hints.get(key)
            if isinstance(value, str) and value.strip():
                filter_hints[key] = value.strip()[:64]
            else:
                filter_hints.pop(key, None)
    for key, value in normalized_filters.items():
        if value and key in ENTITY_FILTER_KEYS:
            filter_hints[key] = value

    order_metric = intent.get("order_metric")
    if order_metric not in METRICS:
        order_metric = metrics[0]
    wants_share = intent.get("wants_share") is True or analysis_type == "share"
    if wants_share and "revenue" not in metrics:
        metrics.insert(0, "revenue")

    sort_direction = intent.get("sort_direction")
    if sort_direction not in SORT_DIRECTIONS:
        sort_direction = fallback["sort_direction"]
    limit = intent.get("limit")
    if not isinstance(limit, int):
        limit = fallback["limit"]
    if analysis_type == "trend" and not has_explicit_limit(question):
        limit = max(limit, 36)

    confidence = intent.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = fallback["confidence"]
    confidence = max(0.0, min(1.0, float(confidence)))

    assumptions = normalize_text_list(intent.get("assumptions"), 6, 120)
    clarifications = intent.get("clarifications")
    normalized_clarifications = clarifications if isinstance(clarifications, list) else []
    narrative_goal = intent.get("narrative_goal")
    if not isinstance(narrative_goal, str) or not narrative_goal.strip():
        narrative_goal = question[:200]

    return {
        "version": "2",
        "analysis_type": analysis_type,
        "time_range": time_range,
        "comparison": comparison or {"mode": "none", "label": "不对比"},
        "filters": normalized_filters,
        "filter_hints": filter_hints,
        "dimensions": dimensions,
        "metrics": metrics[:5],
        "order_metric": order_metric,
        "wants_share": wants_share,
        "sort_direction": sort_direction,
        "limit": max(1, min(50, limit)),
        "confidence": confidence,
        "assumptions": assumptions,
        "clarifications": normalized_clarifications[:8],
        "narrative_goal": narrative_goal.strip()[:200],
    }


def valid_iso_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def normalize_text_list(value: Any, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:item_limit] for item in value[:limit] if str(item).strip()]


def resolve_filter_entities(
    question: str,
    intent: dict[str, Any],
    catalogs: dict[str, list[str]],
    *,
    confirmed: bool = False,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    filters = {key: str(value or "").strip() for key, value in (intent.get("filters") or {}).items()}
    hints = intent.get("filter_hints") if isinstance(intent.get("filter_hints"), dict) else {}
    clarifications: list[dict[str, Any]] = []

    for raw_item in intent.get("clarifications") or []:
        if isinstance(raw_item, str) and raw_item.strip():
            clarifications.append(
                {
                    "field": "intent",
                    "label": "需求存在歧义",
                    "message": raw_item.strip()[:160],
                    "candidates": [],
                }
            )
        elif isinstance(raw_item, dict) and raw_item.get("message"):
            clarifications.append(dict(raw_item))

    for field in ENTITY_FILTER_KEYS:
        desired = str(filters.get(field) or hints.get(field) or "").strip()
        candidates = [str(value).strip() for value in catalogs.get(field, []) if str(value).strip()]
        if desired:
            matches = ranked_entity_matches(desired, candidates)
            if not matches:
                clarifications.append(
                    {
                        "field": field,
                        "label": FILTER_LABELS[field],
                        "message": f"没有找到与“{desired}”匹配的{FILTER_LABELS[field]}，请修改或取消该条件。",
                        "value": desired,
                        "candidates": [],
                    }
                )
                continue
            best_score = matches[0][1]
            best = [value for value, score in matches if score >= best_score - 0.04]
            if len(best) > 1 and best_score < 1:
                clarifications.append(
                    {
                        "field": field,
                        "label": FILTER_LABELS[field],
                        "message": f"“{desired}”匹配到多个{FILTER_LABELS[field]}，请选择一个。",
                        "value": desired,
                        "candidates": best[:6],
                    }
                )
                continue
            filters[field] = best[0]
            continue

        embedded = sorted(
            {value for value in candidates if len(normalize_question(value)) >= 2 and normalize_question(value) in normalize_question(question)},
            key=len,
            reverse=True,
        )
        if embedded:
            filters[field] = embedded[0]

    if float(intent.get("confidence") or 0) < 0.75 and not confirmed and not clarifications:
        clarifications.append(
            {
                "field": "intent",
                "label": "分析口径确认",
                "message": "系统对这次需求的理解置信度较低，请核对识别出的时间、筛选条件、维度和指标。",
                "candidates": [],
            }
        )
    return filters, clarifications[:8]


def ranked_entity_matches(value: str, candidates: list[str]) -> list[tuple[str, float]]:
    normalized_value = normalize_question(value)
    ranked: list[tuple[str, float]] = []
    for candidate in candidates:
        normalized_candidate = normalize_question(candidate)
        if normalized_candidate == normalized_value:
            score = 1.0
        elif normalized_value in normalized_candidate or normalized_candidate in normalized_value:
            score = 0.92
        else:
            score = SequenceMatcher(None, normalized_value, normalized_candidate).ratio()
        if score >= 0.62:
            ranked.append((candidate, score))
    ranked.sort(key=lambda item: (item[1], len(item[0])), reverse=True)
    return ranked[:8]


def collapse_filtered_dimensions(question: str, intent: dict[str, Any]) -> list[str]:
    dimensions = list(intent.get("dimensions") or [])
    filters = intent.get("filters") or {}
    text = normalize_question(question)
    dimension_filters = {
        "category": "category",
        "product_classification": "product_classification",
        "product": "product",
        "platform": "platform",
        "shop": "shop_name",
        "dept": "dept",
        "province": "province",
        "city": "city",
        "order_source": "order_source",
    }
    group_words = {
        "category": ("各大类", "按大类", "各品类", "按品类"),
        "product_classification": ("各货品分类", "按货品分类"),
        "product": ("各产品", "按产品", "各商品", "按商品"),
        "platform": ("各平台", "按平台", "不同平台"),
        "shop": ("各店铺", "按店铺", "不同店铺"),
        "dept": ("各部门", "按部门", "各大区"),
        "province": ("各省", "按省", "各地区"),
        "city": ("各城市", "按城市"),
        "order_source": ("各订单来源", "按订单来源"),
    }
    result: list[str] = []
    for dimension in dimensions:
        filter_key = dimension_filters.get(dimension)
        explicitly_grouped = any(word in text for word in group_words.get(dimension, ()))
        if filter_key and filters.get(filter_key) and not explicitly_grouped and len(dimensions) > 1:
            continue
        result.append(dimension)
    return result or dimensions[:1] or ["product"]


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
    v2_intent = normalize_analysis_intent_v2(intent, question) if intent and str(intent.get("version")) == "2" else None
    normalized_intent = normalize_analysis_intent(intent) if intent and not v2_intent else None
    if v2_intent:
        dimensions = v2_intent["dimensions"]
        metrics = v2_intent["metrics"]
        order_metric = v2_intent["order_metric"]
        wants_share = v2_intent["wants_share"]
        sort_direction = v2_intent["sort_direction"]
        limit = v2_intent["limit"]
    elif normalized_intent:
        dimensions = normalized_intent["dimensions"]
        metrics = normalized_intent["metrics"]
        order_metric = normalized_intent["order_metric"]
        wants_share = normalized_intent["wants_share"]
        sort_direction = "desc"
        limit = 60
    else:
        dimensions = detect_dimensions(question)
        metrics, order_metric, wants_share = detect_metrics(question)
        sort_direction = detect_sort_direction(question)
        limit = detect_limit(question)
    if order_metric not in metrics and order_metric in METRICS:
        metrics.insert(0, order_metric)

    select_parts = [DIMENSIONS[key].select_sql for key in dimensions]
    select_parts.extend(METRICS[key].select_sql for key in metrics)
    share_total_join = ""
    if wants_share:
        # MySQL 5.7 and older MariaDB releases do not support window functions.
        # Compute the filtered grand total once in a one-row derived table, then
        # wrap it in MAX() so the outer grouped query also satisfies
        # ONLY_FULL_GROUP_BY.
        share_total_join = f"""
                CROSS JOIN (
                  SELECT COALESCE(SUM(o.share_receivable), 0) AS total_revenue
                  FROM t_order_sku_detail o
                  {where}
                ) share_totals
                """
        select_parts.append(
            "CASE WHEN MAX(share_totals.total_revenue) = 0 THEN 0 "
            "ELSE SUM(o.share_receivable) / MAX(share_totals.total_revenue) * 100 END AS revenue_share_pct"
        )

    group_parts = []
    for key in dimensions:
        group_parts.extend(part.strip() for part in DIMENSIONS[key].group_sql.split(","))
    group_by = ", ".join(group_parts)
    order_by = "month ASC" if dimensions == ["month"] else f"{order_metric} {sort_direction.upper()}"
    if len(dimensions) > 1:
        limit = min(120, max(limit, 30))
    else:
        limit = min(50, limit)

    sql = f"""
                SELECT
                  {", ".join(select_parts)}
                FROM t_order_sku_detail o
                {share_total_join}
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
        "sort_direction": sort_direction,
        "limit": limit,
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


def comparison_rows(
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    dimensions = plan["dimensions"]
    metric = plan["order_metric"]
    previous_by_key = {row_identity(row, dimensions): row for row in previous_rows}
    result: list[dict[str, Any]] = []
    for row in current_rows:
        previous = previous_by_key.get(row_identity(row, dimensions), {})
        current_value = to_float(row.get(metric))
        previous_value = to_float(previous.get(metric))
        change_pct = None if previous_value == 0 else (current_value - previous_value) / abs(previous_value) * 100
        result.append(
            {
                "label": row_label(row, dimensions),
                "current": current_value,
                "previous": previous_value,
                "change": current_value - previous_value,
                "change_pct": change_pct,
            }
        )
    result.sort(key=lambda item: item["change"], reverse=plan.get("sort_direction") != "asc")
    return result


def row_identity(row: dict[str, Any], dimensions: list[str]) -> tuple[str, ...]:
    values: list[str] = []
    for key in dimensions:
        if key == "product":
            values.append(str(row.get("product_no") or row.get("product_name") or ""))
        elif key == "customer":
            values.append(str(row.get("customer_no") or row.get("customer_name") or ""))
        elif key == "shop":
            values.append(str(row.get("shop_name") or ""))
        else:
            values.append(str(row.get(key) or ""))
    return tuple(values)


def build_structured_insights(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    intent: dict[str, Any],
    compared_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "kind": "empty",
                "title": "当前口径暂无数据",
                "summary": "建议核对时间范围与筛选条件，或扩大查询范围后重试。",
                "evidence": [],
            }
        ]

    metric = "revenue_share_pct" if plan["wants_share"] else plan["order_metric"]
    first = rows[0]
    first_label = row_label(first, plan["dimensions"])
    first_value = to_float(first.get(metric))
    insights: list[dict[str, Any]] = [
        {
            "kind": "ranking",
            "title": "首要发现",
            "summary": (
                f"{first_label} 的{chart_metric_name(metric)}为 "
                f"{first_value:.2f}{'%' if metric in ('revenue_share_pct', 'profit_rate') else ''}。"
            ),
            "evidence": [
                {
                    "label": first_label,
                    "metric": metric,
                    "value": first_value,
                }
            ],
        }
    ]

    if compared_rows:
        total_current = sum(item["current"] for item in compared_rows)
        total_previous = sum(item["previous"] for item in compared_rows)
        total_change_pct = None if total_previous == 0 else (total_current - total_previous) / abs(total_previous) * 100
        driver = max(compared_rows, key=lambda item: abs(item["change"]))
        trend_word = "增长" if total_current >= total_previous else "下降"
        change_text = "无法计算百分比" if total_change_pct is None else f"{abs(total_change_pct):.2f}%"
        insights.append(
            {
                "kind": "comparison",
                "title": "周期对比",
                "summary": f"当前展示项合计较对比周期{trend_word}{change_text}，变化最大的项目是 {driver['label']}。",
                "evidence": [
                    {
                        "label": driver["label"],
                        "current": driver["current"],
                        "previous": driver["previous"],
                        "change": driver["change"],
                        "change_pct": driver["change_pct"],
                    }
                ],
            }
        )

    if intent.get("analysis_type") in {"diagnosis", "contribution"}:
        profit_rows = [row for row in rows if "profit" in row]
        if profit_rows:
            weakest = min(profit_rows, key=lambda row: to_float(row.get("profit")))
            weakest_label = row_label(weakest, plan["dimensions"])
            weakest_profit = to_float(weakest.get("profit"))
            action = (
                "优先核对售价、成本及分摊费用，并细分到店铺或产品继续分析。"
                if weakest_profit < 0
                else "建议结合销售额与利润率继续观察低贡献项目。"
            )
            insights.append(
                {
                    "kind": "diagnosis",
                    "title": "风险与下一步",
                    "summary": f"{weakest_label} 的利润表现最弱，利润为 {weakest_profit:.2f}。{action}",
                    "evidence": [{"label": weakest_label, "metric": "profit", "value": weakest_profit}],
                }
            )
    return insights[:4]


def summarize_insights(insights: list[dict[str, Any]]) -> str:
    summaries = [str(item.get("summary") or "").strip() for item in insights if item.get("summary")]
    return " ".join(summaries[:3]) or "分析已完成，请查看图表和明细。"


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
