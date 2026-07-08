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
    "渠道分类",
    "渠道平台",
    "销售渠道",
    "订单编号",
    "网店订单号（新）",
    "物流公司",
    "物流单号",
    "收货人",
    "地址",
    "电话",
    "大类",
    "货品名称",
    "货品编号",
    "单位",
    "数量",
    "销售额",
    "省",
    "市",
    "县",
    "发货时间",
    "成本金额",
    "快递费",
    "物流费",
    "运费",
    "辅料费用",
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
        "浙江省杭州市余杭区未来科技城示例路 1 号",
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
        "广东省广州市天河区珠江新城示例路 2 号",
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
