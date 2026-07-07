from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


HEADERS = [
    "商品链接Id",
    "商品链接SkuId",
    "订单来源",
    "客户编号",
    "客户名称",
    "部门",
    "平台渠道",
    "店铺",
    "订单编号",
    "原始单号",
    "物流方式",
    "物流单号",
    "收货人",
    "电话",
    "大类",
    "产品名称",
    "货品编号",
    "单位",
    "数量",
    "应收合计分摊",
    "州省",
    "区市",
    "区县",
    "发货时间",
    "成本",
    "快递费",
    "物流费",
    "运费",
    "辅料",
    "分摊费用",
    "利润",
]


ROWS = [
    [
        "L001",
        "SKU-001",
        "线上订单",
        "C001",
        "杭州样例客户",
        "华东事业部",
        "天猫",
        "旗舰店",
        "ORD-202607-001",
        "",
        "快递",
        "SF10001",
        "张三",
        "13800000001",
        "家居",
        "收纳箱 45L",
        "P-BOX-45",
        "个",
        2,
        198,
        "浙江",
        "杭州",
        "余杭区",
        datetime(2026, 7, 1, 10, 30),
        92,
        12,
        0,
        8,
        3,
        5,
        90,
    ],
    [
        "L002",
        "SKU-002",
        "线上订单",
        "C002",
        "广州样例客户",
        "华南事业部",
        "京东",
        "自营店",
        "ORD-202607-002",
        "",
        "物流",
        "YD10002",
        "李四",
        "13900000002",
        "个护",
        "旅行洗漱包",
        "P-BAG-01",
        "个",
        5,
        245,
        "广东",
        "广州",
        "天河区",
        datetime(2026, 7, 2, 15, 0),
        125,
        20,
        5,
        10,
        8,
        7,
        95,
    ],
]


def main() -> None:
    out_dir = Path("sample_data")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "orders_sample.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HEADERS)
    for row in ROWS:
        ws.append(row)
    wb.save(path)
    print(path.resolve())


if __name__ == "__main__":
    main()
