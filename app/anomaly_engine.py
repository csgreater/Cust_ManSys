"""Deterministic anomaly calculation and report assembly.

All monetary and quantity calculations stay as ``Decimal`` values.  The
database is queried without presentation limits; pagination belongs at the API
boundary, after this module has produced a complete authorized snapshot.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from app.import_access import import_batch_access_clause
from app.permissions import has_permission


DEFAULT_RULES = {
    "low_margin_pct": 5,
    "high_fee_pct": 20,
    "decline_pct": 20,
    "min_revenue": 1000,
}

GROUP_FIELDS = (
    "dept",
    "platform",
    "shop_name",
    "product_no",
    "category",
    "product_classification",
)

RULE_LABELS = {
    "negative_profit": "负利润",
    "low_margin": "低利润率",
    "high_fee": "扣减费用率偏高",
    "revenue_decline": "销售额下降",
    "profit_decline": "利润下降",
    "data_error": "数据校验错误",
    "data_warning": "数据校验警告",
}

PHONE_RE = re.compile(r"(?<!\d)(1\d{2})\d{4}(\d{4})(?!\d)")
SENSITIVE_DIAGNOSTIC_RE = re.compile(
    r"(?i)((?:receiver_name|receiver_address|receiver_phone|收货人|收件人|收货地址|地址|电话|手机号|手机)"
    r"(?:(?:(?![；;\n]).)*?原值)?\s*[:：=]\s*)([^；;\n]+)"
)


def _comparison_period(filters: dict[str, Any]) -> dict[str, Any]:
    from app.analysis_periods import comparison_period

    return comparison_period(filters)


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _plain_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def normalize_rules(value: dict[str, Any]) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise ValueError("异常规则必须是对象")
    unknown = set(value) - set(DEFAULT_RULES)
    if unknown:
        raise ValueError(f"未知异常规则：{', '.join(sorted(unknown))}")
    result: dict[str, int | float] = {}
    for key, default in DEFAULT_RULES.items():
        raw = value.get(key, default)
        if isinstance(raw, bool):
            raise ValueError(f"{key} 必须是有效数字")
        try:
            number = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{key} 必须是有效数字") from exc
        if not number.is_finite() or number < 0:
            raise ValueError(f"{key} 不得为负数、NaN 或无穷大")
        if key.endswith("_pct") and number > 100:
            raise ValueError(f"{key} 必须在 0 到 100 之间")
        result[key] = _plain_number(number)
    return result


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return format(normalized, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rules_version(rules: dict[str, Any]) -> str:
    """Return the canonical full digest used by storage and snapshots."""
    return _hash(normalize_rules(rules))


def _group_key(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in GROUP_FIELDS)


def _normalize_group(row: dict[str, Any]) -> dict[str, Any]:
    result = {field: str(row.get(field) or "") for field in GROUP_FIELDS}
    result["product_name"] = str(row.get("product_name") or "")
    for field in ("qty", "revenue", "profit", "fees", "express_fee", "logistics_fee"):
        result[field] = _decimal(row.get(field))
    result["detail_rows"] = int(row.get("detail_rows") or 0)
    return result


def visible_diagnostic(value: Any) -> str:
    text = str(value or "")
    text = SENSITIVE_DIAGNOSTIC_RE.sub(lambda match: f"{match.group(1)}[已隐藏]", text)
    return PHONE_RE.sub(r"\1****\2", text)


def _fetch_period(
    conn,
    user: dict[str, Any],
    filters: dict[str, Any],
    where_builder: Callable[..., tuple[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    where, params = where_builder(user, filters, alias="o", validate_dates=True)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            /* anomaly:groups */
            SELECT
              o.dept, o.platform, o.shop_name, o.product_no, o.category,
              o.product_classification, MAX(o.product_name) AS product_name,
              COALESCE(SUM(o.qty), 0) AS qty,
              COALESCE(SUM(o.share_receivable), 0) AS revenue,
              COALESCE(SUM(
                o.share_receivable - o.cost - o.freight - o.aux_material - o.share_cost
              ), 0) AS profit,
              COALESCE(SUM(o.freight + o.aux_material + o.share_cost), 0) AS fees,
              COALESCE(SUM(o.express_fee), 0) AS express_fee,
              COALESCE(SUM(o.logistics_fee), 0) AS logistics_fee,
              COUNT(*) AS detail_rows
            FROM t_order_sku_detail o
            {where}
            GROUP BY o.dept, o.platform, o.shop_name, o.product_no,
                     o.category, o.product_classification
            ORDER BY o.dept, o.platform, o.shop_name, o.product_no,
                     o.category, o.product_classification
            """,
            params,
        )
        groups = sorted(
            (_normalize_group(row) for row in cur.fetchall()),
            key=_group_key,
        )
        cur.execute(
            f"""
            /* anomaly:orders */
            SELECT COUNT(DISTINCT o.order_no) AS orders
            FROM t_order_sku_detail o
            {where}
            """,
            params,
        )
        order_row = cur.fetchone() or {}
    return groups, int(order_row.get("orders") or 0)


def _summarize(groups: list[dict[str, Any]], orders: int) -> dict[str, Any]:
    summary = {
        "revenue": sum((row["revenue"] for row in groups), Decimal("0")),
        "profit": sum((row["profit"] for row in groups), Decimal("0")),
        "qty": sum((row["qty"] for row in groups), Decimal("0")),
        "fees": sum((row["fees"] for row in groups), Decimal("0")),
        "detail_rows": sum(row["detail_rows"] for row in groups),
        "orders": orders,
    }
    summary["profit_rate"] = (
        summary["profit"] / summary["revenue"] * Decimal("100")
        if summary["revenue"]
        else None
    )
    summary["fee_rate"] = (
        summary["fees"] / summary["revenue"] * Decimal("100")
        if summary["revenue"]
        else None
    )
    return summary


def _object_label(row: dict[str, Any]) -> str:
    product = row.get("product_name") or row.get("product_no") or "未命名商品"
    code = row.get("product_no") or "无货号"
    shop = row.get("shop_name") or "未命名店铺"
    return f"{product}（{code}） / {shop}"


def _contributions(
    current_groups: list[dict[str, Any]], previous_groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    current = {_group_key(row): row for row in current_groups}
    previous = {_group_key(row): row for row in previous_groups}
    rows: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(previous)):
        cur = current.get(key)
        prev = previous.get(key)
        identity = cur or prev or {}
        row = {field: identity.get(field, "") for field in GROUP_FIELDS}
        row["product_name"] = identity.get("product_name", "")
        row["object_label"] = _object_label(identity)
        row["current_revenue"] = cur["revenue"] if cur else Decimal("0")
        row["previous_revenue"] = prev["revenue"] if prev else Decimal("0")
        row["revenue_change"] = row["current_revenue"] - row["previous_revenue"]
        row["current_profit"] = cur["profit"] if cur else Decimal("0")
        row["previous_profit"] = prev["profit"] if prev else Decimal("0")
        row["profit_change"] = row["current_profit"] - row["previous_profit"]
        row["current_qty"] = cur["qty"] if cur else Decimal("0")
        row["previous_qty"] = prev["qty"] if prev else Decimal("0")
        row["qty_change"] = row["current_qty"] - row["previous_qty"]
        row["disappeared"] = cur is None and prev is not None
        row["new_in_period"] = cur is not None and prev is None
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            -max(abs(row["revenue_change"]), abs(row["profit_change"])),
            tuple(str(row.get(field) or "") for field in GROUP_FIELDS),
        ),
    )


def _change_pct(current: Decimal, baseline: Decimal) -> Decimal | None:
    if baseline == 0:
        return None
    return (current - baseline) / abs(baseline) * Decimal("100")


def _severity(rule_id: str, impact: Decimal, reference: Decimal) -> str:
    if rule_id == "negative_profit":
        return "high"
    if reference > 0 and impact >= reference * Decimal("0.5"):
        return "high"
    return "medium"


def _operating_exception(
    *,
    rule_id: str,
    current: dict[str, Any] | None,
    previous: dict[str, Any] | None,
    current_value: Decimal,
    baseline_value: Decimal | None,
    change_pct: Decimal | None,
    impact: Decimal,
    message: str,
    suggestion: str,
    context: dict[str, Any],
    severity_reference: Decimal | None = None,
) -> dict[str, Any]:
    identity = current or previous or {}
    id_payload = {
        "type": "operating",
        "rule_id": rule_id,
        "group": {field: identity.get(field, "") for field in GROUP_FIELDS},
        "period": context["period"],
        "filters": context["filters"],
        "rules": context["rules"],
    }
    evidence = {
        "group": {field: identity.get(field, "") for field in GROUP_FIELDS},
        "current": current,
        "previous": previous,
        "rule": {"id": rule_id, "rules": context["rules"]},
        "period": context["period"],
        "comparison": context["comparison"],
        "filters": context["filters"],
    }
    result = {
        "id": f"op-{_hash(id_payload)[:24]}",
        "type": "operating",
        "rule_id": rule_id,
        "rule_label": RULE_LABELS[rule_id],
        "severity": _severity(
            rule_id,
            impact,
            severity_reference if severity_reference is not None else abs(baseline_value or current_value),
        ),
        "object_label": _object_label(identity),
        "platform": identity.get("platform", ""),
        "shop_name": identity.get("shop_name", ""),
        "product_no": identity.get("product_no", ""),
        "current_value": current_value,
        "baseline_value": baseline_value,
        "change_pct": change_pct,
        "impact_amount": max(impact, Decimal("0")),
        "message": message,
        "suggestion": suggestion,
        "evidence": evidence,
    }
    result["evidence_hash"] = _hash(evidence)
    return result


def _operating_rows(
    current_groups: list[dict[str, Any]],
    previous_groups: list[dict[str, Any]],
    *,
    filters: dict[str, Any],
    rules: dict[str, Any],
    comparison: dict[str, Any],
) -> list[dict[str, Any]]:
    current = {_group_key(row): row for row in current_groups}
    previous = {_group_key(row): row for row in previous_groups}
    low_margin = _decimal(rules["low_margin_pct"])
    high_fee = _decimal(rules["high_fee_pct"])
    decline = _decimal(rules["decline_pct"])
    min_revenue = _decimal(rules["min_revenue"])
    context = {
        "filters": filters,
        "rules": rules,
        "period": {"start_time": filters.get("start_time"), "end_time": filters.get("end_time")},
        "comparison": comparison,
    }
    rows: list[dict[str, Any]] = []
    for key in sorted(set(current) | set(previous)):
        cur = current.get(key)
        prev = previous.get(key)
        revenue = cur["revenue"] if cur else Decimal("0")
        profit = cur["profit"] if cur else Decimal("0")
        fees = cur["fees"] if cur else Decimal("0")
        margin_pct = profit / revenue * Decimal("100") if revenue else None
        fee_pct = fees / revenue * Decimal("100") if revenue else None

        if cur and profit < 0:
            rows.append(_operating_exception(
                rule_id="negative_profit", current=cur, previous=prev,
                current_value=profit, baseline_value=prev["profit"] if prev else None,
                change_pct=_change_pct(profit, prev["profit"]) if prev else None,
                impact=-profit, message=f"本期利润为 {profit}，触发负利润规则。",
                suggestion="核对售价、成本、运费、辅料和分摊费用。", context=context,
            ))
        if cur and revenue >= min_revenue and margin_pct is not None and margin_pct < low_margin:
            rows.append(_operating_exception(
                rule_id="low_margin", current=cur, previous=prev,
                current_value=margin_pct,
                baseline_value=(prev["profit"] / prev["revenue"] * Decimal("100")) if prev and prev["revenue"] else None,
                change_pct=None,
                impact=max(revenue * (low_margin - margin_pct) / Decimal("100"), Decimal("0")),
                message=f"本期利润率为 {margin_pct}%，低于参考阈值 {low_margin}%。",
                suggestion="核对收入、产品成本和利润公式中的扣减费用。", context=context,
                severity_reference=abs(revenue),
            ))
        if cur and revenue >= min_revenue and fee_pct is not None and fee_pct > high_fee:
            rows.append(_operating_exception(
                rule_id="high_fee", current=cur, previous=prev,
                current_value=fee_pct,
                baseline_value=(prev["fees"] / prev["revenue"] * Decimal("100")) if prev and prev["revenue"] else None,
                change_pct=None,
                impact=max(fees - revenue * high_fee / Decimal("100"), Decimal("0")),
                message=f"本期扣减费用率为 {fee_pct}%，高于参考阈值 {high_fee}%。",
                suggestion="核对运费、辅料和分摊费用；快递费与物流费仅作旁证。", context=context,
                severity_reference=abs(revenue),
            ))

        if current_groups and prev and prev["revenue"] > 0 and prev["revenue"] >= min_revenue:
            revenue_change_pct = _change_pct(revenue, prev["revenue"])
            if revenue_change_pct is not None and revenue_change_pct <= -decline:
                rows.append(_operating_exception(
                    rule_id="revenue_decline", current=cur, previous=prev,
                    current_value=revenue, baseline_value=prev["revenue"],
                    change_pct=revenue_change_pct, impact=prev["revenue"] - revenue,
                    message=f"销售额较有效基线下降 {abs(revenue_change_pct)}%。",
                    suggestion="核对商品状态、供货、活动和渠道变化；当前数据不能证明具体原因。", context=context,
                ))
        volume_base = max(revenue, prev["revenue"] if prev else Decimal("0"))
        if current_groups and prev and prev["profit"] > 0 and volume_base >= min_revenue:
            profit_change_pct = _change_pct(profit, prev["profit"])
            if profit_change_pct is not None and profit_change_pct <= -decline:
                rows.append(_operating_exception(
                    rule_id="profit_decline", current=cur, previous=prev,
                    current_value=profit, baseline_value=prev["profit"],
                    change_pct=profit_change_pct, impact=prev["profit"] - profit,
                    message=f"利润较有效基线下降 {abs(profit_change_pct)}%。",
                    suggestion="核对收入、成本和扣减费用变化；当前数据不能证明具体原因。", context=context,
                ))

    return sorted(rows, key=lambda row: (-row["impact_amount"], row["rule_id"], row["id"]))


def _quality_where(filters: dict[str, Any], params: dict[str, Any]) -> str:
    clauses: list[str] = []
    batch_no = filters.get("batch_no") or filters.get("batch")
    if batch_no:
        params["batch_no"] = batch_no
        clauses.append("t.batch_no = %(batch_no)s")
    for key, field in (
        ("dept", "dept"), ("platform", "platform"), ("shop_name", "shop_name"),
        ("category", "category"), ("product_classification", "product_classification"),
        ("province", "province"), ("city", "city"), ("order_source", "order_source"),
    ):
        if filters.get(key):
            params[f"quality_{key}"] = filters[key]
            clauses.append(f"t.{field} = %(quality_{key})s")
    if filters.get("product"):
        params["quality_product"] = f"%{filters['product']}%"
        clauses.append("(t.product_name LIKE %(quality_product)s OR t.product_no LIKE %(quality_product)s OR t.sku_id LIKE %(quality_product)s)")
    if filters.get("order_no"):
        params["quality_order_no"] = f"%{filters['order_no']}%"
        clauses.append("t.order_no LIKE %(quality_order_no)s")
    return "".join(f" AND {clause}" for clause in clauses)


def _fetch_quality_rows(conn, user: dict[str, Any], filters: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, Any]]:
    if not has_permission(user, "import"):
        return []
    params: dict[str, Any] = {}
    access = import_batch_access_clause(user, params, alias="l")
    quality_filters = _quality_where(filters, params)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            /* anomaly:quality */
            SELECT t.batch_no, t.row_no, t.error_message, t.warning_message
            FROM tmp_order_import t
            JOIN t_import_log l ON l.batch_no = t.batch_no
            WHERE (COALESCE(t.error_message, '') <> '' OR COALESCE(t.warning_message, '') <> '')
            {access}
            {quality_filters}
            ORDER BY t.batch_no, t.row_no
            """,
            params,
        )
        source_rows = list(cur.fetchall())

    context = {"filters": filters, "rules": rules}
    rows = []
    for source in source_rows:
        error_message = visible_diagnostic(source.get("error_message"))
        warning_message = visible_diagnostic(source.get("warning_message"))
        rule_id = "data_error" if error_message else "data_warning"
        evidence = {
            "batch_no": str(source.get("batch_no") or ""),
            "row_no": int(source.get("row_no") or 0),
            "error_message": error_message,
            "warning_message": warning_message,
        }
        identity = {"type": "quality", "rule_id": rule_id, "evidence": evidence, **context}
        rows.append({
            "id": f"dq-{_hash(identity)[:24]}",
            "type": "quality",
            "rule_id": rule_id,
            "rule_label": RULE_LABELS[rule_id],
            "severity": "high" if error_message else "low",
            "object_label": f"批次 {evidence['batch_no']} 第 {evidence['row_no']} 行",
            "platform": "",
            "shop_name": "",
            "product_no": "",
            "current_value": error_message or warning_message,
            "baseline_value": None,
            "change_pct": None,
            "impact_amount": Decimal("0"),
            "message": error_message or warning_message,
            "suggestion": "按校验信息修正源文件后重新上传。" if error_message else "复核提示项，确认无误后再入库。",
            "evidence_hash": _hash({"evidence": evidence, **context}),
            "evidence": evidence,
        })
    return rows


def _narrative(
    summary: dict[str, Any],
    previous: dict[str, Any],
    contributions: list[dict[str, Any]],
    *,
    current_has_records: bool,
) -> list[str]:
    lines: list[str] = []
    if not current_has_records:
        lines.append("本期无经营记录，无法确认零经营还是未导入，因此不生成下降结论。")
    elif previous["revenue"]:
        change = _change_pct(summary["revenue"], previous["revenue"])
        direction = "上升" if change is not None and change >= 0 else "下降"
        display_change = abs(change or Decimal("0")).quantize(Decimal("0.01"))
        lines.append(f"本期销售额较对比期{direction} {display_change:.2f}%。")
    else:
        lines.append("对比期销售额为零或缺失，不生成销售额下降结论。")
    lines.append(f"本期利润为 {summary['profit']}，与对比期的数值差额为 {summary['profit'] - previous['profit']}。")
    if contributions:
        lines.append("变化贡献按产品与店铺分组的数值差额排列，不代表已验证的业务原因。")
    return lines


def build_snapshot(
    conn,
    user: dict[str, Any],
    filters: dict[str, Any],
    rules: dict[str, Any],
    where_builder: Callable[..., tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    normalized_rules = normalize_rules(rules)
    current_filters = copy.deepcopy(filters)
    comparison = _comparison_period(current_filters)
    previous_filters = copy.deepcopy(current_filters)
    previous_filters["start_time"] = comparison["start_time"]
    previous_filters["end_time"] = comparison["end_time"]

    current_groups, current_orders = _fetch_period(conn, user, current_filters, where_builder)
    previous_groups, previous_orders = _fetch_period(conn, user, previous_filters, where_builder)
    summary = _summarize(current_groups, current_orders)
    previous_summary = _summarize(previous_groups, previous_orders)
    contributions = _contributions(current_groups, previous_groups)
    operating_rows = _operating_rows(
        current_groups,
        previous_groups,
        filters=current_filters,
        rules=normalized_rules,
        comparison=comparison,
    )
    quality_rows = _fetch_quality_rows(conn, user, current_filters, normalized_rules)

    current_where, current_params = where_builder(user, current_filters, alias="o", validate_dates=True)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            /* anomaly:latest */
            SELECT MAX(o.ship_time) AS latest_data_at
            FROM t_order_sku_detail o
            {current_where}
            """,
            current_params,
        )
        latest_data_at = (cur.fetchone() or {}).get("latest_data_at")

    impact_by_rule: dict[str, Decimal] = {}
    count_by_rule: dict[str, int] = {}
    for row in operating_rows:
        impact_by_rule[row["rule_id"]] = impact_by_rule.get(row["rule_id"], Decimal("0")) + row["impact_amount"]
        count_by_rule[row["rule_id"]] = count_by_rule.get(row["rule_id"], 0) + 1
    summary["operating_exception_count"] = len(operating_rows)
    summary["quality_exception_count"] = len(quality_rows)
    summary["impact_by_rule"] = impact_by_rule
    summary["count_by_rule"] = count_by_rule

    current_keys = {_group_key(row) for row in current_groups}
    previous_by_key = {_group_key(row): row for row in previous_groups}
    missing_baselines = sum(1 for row in current_groups if _group_key(row) not in previous_by_key)
    zero_baselines = sum(1 for row in current_groups if previous_by_key.get(_group_key(row), {}).get("revenue") == 0)
    disappeared = len(set(previous_by_key) - current_keys)
    warnings = [
        "扣减费用率仅包含利润公式中的运费、辅料和分摊费用，不含产品成本；快递费和物流费因重叠口径未确认，仅保留为证据。"
    ]
    if not previous_groups:
        warnings.append("对比期没有可用经营数据，不生成下降结论。")
    if missing_baselines:
        warnings.append(f"{missing_baselines} 个本期对象缺少对比基线，未生成其下降结论。")
    if zero_baselines:
        warnings.append(f"{zero_baselines} 个对象的对比期销售额为零，未生成销售额下降结论。")
    if disappeared:
        if current_groups:
            warnings.append(f"{disappeared} 个对比期对象在本期未出现，已按零值纳入变化贡献与下降判断。")
        else:
            warnings.append("本期无经营记录，无法确认零经营还是未导入；对比期对象仅纳入数值贡献，不生成下降异常。")

    data_basis = {
        "current_groups": current_groups,
        "previous_groups": previous_groups,
        "orders": [current_orders, previous_orders],
        "quality_rows": quality_rows,
        "latest_data_at": latest_data_at,
    }
    return {
        "filters": current_filters,
        "comparison": copy.deepcopy(comparison),
        "summary": summary,
        "previous_summary": previous_summary,
        "contributions": contributions,
        "operating_rows": operating_rows,
        "quality_rows": quality_rows,
        "rules": normalized_rules,
        "rules_version": rules_version(normalized_rules),
        "data_version": f"data-{_hash(data_basis)[:20]}",
        "warnings": warnings,
        "narrative": _narrative(
            summary,
            previous_summary,
            contributions,
            current_has_records=bool(current_groups),
        ),
        "latest_data_at": latest_data_at,
    }


def build_report(snapshot: dict[str, Any], report_type: str, title: str) -> dict[str, Any]:
    if report_type not in {"monthly", "exception"}:
        raise ValueError("report_type 必须是 monthly 或 exception")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("报告标题不能为空")
    result = {
        "title": title.strip(),
        "report_type": report_type,
    }
    for key in (
        "filters", "comparison", "summary", "previous_summary", "contributions",
        "operating_rows", "quality_rows", "rules", "rules_version", "data_version",
        "warnings", "narrative", "latest_data_at",
    ):
        result[key] = copy.deepcopy(snapshot.get(key))

    top_n = 10
    result["sections"] = [
        {"key": "summary", "title": "经营摘要", "summary": copy.deepcopy(result["summary"])},
        {
            "key": "operating",
            "title": f"重点经营异常（Top {top_n}）",
            "top_n": top_n,
            "total": len(result["operating_rows"] or []),
            "rows": copy.deepcopy((result["operating_rows"] or [])[:top_n]),
        },
        {
            "key": "quality",
            "title": f"数据质量异常（Top {top_n}）",
            "top_n": top_n,
            "total": len(result["quality_rows"] or []),
            "rows": copy.deepcopy((result["quality_rows"] or [])[:top_n]),
        },
        {
            "key": "contributions",
            "title": f"变化贡献（Top {top_n}，仅表示数值差额）",
            "top_n": top_n,
            "total": len(result["contributions"] or []),
            "rows": copy.deepcopy((result["contributions"] or [])[:top_n]),
        },
        {
            "key": "methodology",
            "title": "口径与证据",
            "items": [
                "利润 = 分摊应收 - 成本 - 运费 - 辅料 - 分摊费用。",
                "扣减费用率 =（运费 + 辅料 + 分摊费用）/ 销售额。",
                "快递费与物流费未计入扣减费用率，避免在口径未确认前重复计算。",
                "同一对象命中多条规则时分别展示，各规则影响额不可合并为总损失。",
            ],
        },
    ]
    return result
