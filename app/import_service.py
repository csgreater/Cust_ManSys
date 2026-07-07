from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook


HEADER_MAP = {
    "商品链接Id": "link_id",
    "商品链接SkuId": "sku_id",
    "订单来源": "order_source",
    "客户编号": "customer_no",
    "客户名称": "customer_name",
    "部门": "dept",
    "平台渠道": "platform",
    "店铺": "shop_name",
    "订单编号": "order_no",
    "原始单号": "original_order_no",
    "物流方式": "logistics_type",
    "物流单号": "logistics_no",
    "收货人": "receiver_name",
    "电话": "receiver_phone",
    "大类": "category",
    "产品名称": "product_name",
    "货品编号": "product_no",
    "单位": "unit",
    "数量": "qty",
    "应收合计分摊": "share_receivable",
    "州省": "province",
    "区市": "city",
    "区县": "district",
    "发货时间": "ship_time",
    "成本": "cost",
    "快递费": "express_fee",
    "物流费": "logistics_fee",
    "运费": "freight",
    "辅料": "aux_material",
    "分摊费用": "share_cost",
    "利润": "excel_profit",
}

REQUIRED_HEADERS = list(HEADER_MAP.keys())
REQUIRED_FIELDS = {
    "customer_no",
    "customer_name",
    "platform",
    "shop_name",
    "order_no",
    "category",
    "product_name",
    "product_no",
    "unit",
    "qty",
    "share_receivable",
    "ship_time",
    "cost",
}
DECIMAL_FIELDS = {
    "qty",
    "share_receivable",
    "cost",
    "express_fee",
    "logistics_fee",
    "freight",
    "aux_material",
    "share_cost",
    "excel_profit",
}
NON_NEGATIVE_FIELDS = DECIMAL_FIELDS - {"excel_profit"}


@dataclass(frozen=True)
class ImportParseResult:
    batch_no: str
    rows: list[dict[str, Any]]
    total_rows: int
    fail_rows: int
    error_summary: str


def new_batch_no() -> str:
    return f"IMP{datetime.now():%Y%m%d%H%M%S}_{uuid4().hex[:8].upper()}"


def to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("不是有效数字")


def to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("不是有效日期")


def calc_profit(row: dict[str, Any]) -> Decimal:
    return (
        row["share_receivable"]
        - row["cost"]
        - row["freight"]
        - row["aux_material"]
        - row["share_cost"]
    )


def parse_excel(path: Path, batch_no: str | None = None) -> ImportParseResult:
    batch_no = batch_no or new_batch_no()
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not header_row:
            raise ValueError("Excel 文件为空")
        headers = [to_text(value) for value in header_row]
        missing = [header for header in REQUIRED_HEADERS if header not in headers]
        if missing:
            detected = "、".join(header for header in headers if header)
            expected = "、".join(REQUIRED_HEADERS)
            raise ValueError(
                f"Excel 表头不匹配，缺少字段：{', '.join(missing)}。"
                f"当前识别到：{detected or '空表头'}。"
                f"请使用模板字段：{expected}"
            )

        indexes = {HEADER_MAP[header]: headers.index(header) for header in REQUIRED_HEADERS}
        rows: list[dict[str, Any]] = []
        seen_keys: dict[tuple[str, str], int] = {}
        fail_rows = 0

        for row_no, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(value not in (None, "") for value in values):
                continue
            item: dict[str, Any] = {"batch_no": batch_no, "row_no": row_no}
            errors: list[str] = []
            warnings: list[str] = []
            for field, index in indexes.items():
                value = values[index] if index < len(values) else None
                try:
                    if field == "ship_time":
                        item[field] = to_datetime(value)
                    elif field in DECIMAL_FIELDS:
                        item[field] = to_decimal(value)
                    else:
                        item[field] = to_text(value)
                except ValueError as exc:
                    item[field] = Decimal("0") if field in DECIMAL_FIELDS else None
                    errors.append(f"{field}{exc}")

            for field in REQUIRED_FIELDS:
                if item.get(field) in (None, ""):
                    errors.append(f"{field}不能为空")
            for field in NON_NEGATIVE_FIELDS:
                if item.get(field, Decimal("0")) < 0:
                    errors.append(f"{field}不能为负数")
            if item.get("ship_time") is None:
                errors.append("ship_time不能为空")

            order_key = (
                item.get("order_no") or "",
                item.get("sku_id") or item.get("product_no") or "",
            )
            if order_key in seen_keys:
                errors.append(f"本批重复，首次出现行号 {seen_keys[order_key]}")
            elif all(order_key):
                seen_keys[order_key] = row_no

            item["profit"] = calc_profit(item)
            excel_profit = item.get("excel_profit")
            if excel_profit not in (None, "") and abs(item["profit"] - excel_profit) > Decimal("0.05"):
                warnings.append("Excel利润与系统计算利润不一致")

            item["error_message"] = "; ".join(errors)
            item["warning_message"] = "; ".join(warnings)
            if errors:
                fail_rows += 1
            rows.append(item)

        return ImportParseResult(
            batch_no=batch_no,
            rows=rows,
            total_rows=len(rows),
            fail_rows=fail_rows,
            error_summary=f"共 {len(rows)} 行，异常 {fail_rows} 行",
        )
    finally:
        wb.close()
