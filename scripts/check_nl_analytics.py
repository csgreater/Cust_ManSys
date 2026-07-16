from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.nl_analytics import audit_sql_plan, build_chart, build_sql, normalize_analysis_intent, parse_question_filters  # noqa: E402


CASES = [
    {
        "question": "\u4eca\u5e741-5\u6708\u5404\u4ea7\u54c1\u9500\u552e\u989d\u5360\u6bd4",
        "start": "2026-01-01",
        "end": "2026-05-31",
        "dimensions": ["product"],
        "metrics": ["revenue"],
        "share": True,
        "chart": "pie",
    },
    {
        "question": "\u4eca\u5e741-5\u6708\u5404\u5e97\u94fa\u5229\u6da6\u6392\u540d",
        "start": "2026-01-01",
        "end": "2026-05-31",
        "dimensions": ["shop"],
        "metrics": ["profit"],
        "share": False,
        "chart": "bar",
    },
    {
        "question": "\u4eca\u5e741-5\u6708\u6309\u6708\u9500\u552e\u989d\u8d8b\u52bf",
        "start": "2026-01-01",
        "end": "2026-05-31",
        "dimensions": ["month"],
        "metrics": ["revenue"],
        "share": False,
        "chart": "line",
    },
    {
        "question": "今年1-5月各货品分类销售额占比",
        "start": "2026-01-01",
        "end": "2026-05-31",
        "dimensions": ["product_classification"],
        "metrics": ["revenue"],
        "share": True,
        "chart": "pie",
    },
]


def main() -> None:
    today = date(2026, 7, 9)
    for case in CASES:
        filters = parse_question_filters(case["question"], today=today)
        assert filters["start_time"] == case["start"], (case["question"], filters)
        assert filters["end_time"] == case["end"], (case["question"], filters)
        params = {**filters, "end_time_exclusive": "2026-06-01"}
        plan = build_sql(
            case["question"],
            " WHERE o.ship_time >= %(start_time)s AND o.ship_time < %(end_time_exclusive)s",
            params,
        )
        assert plan["dimensions"] == case["dimensions"], (case["question"], plan["dimensions"])
        assert plan["metrics"][: len(case["metrics"])] == case["metrics"], (case["question"], plan["metrics"])
        assert plan["wants_share"] is case["share"], (case["question"], plan["wants_share"])
        audit_sql_plan(plan["sql"], params)
        rows = [{"product_name": "A", "shop_name": "S", "month": "2026-01", "revenue": 100, "profit": -5, "revenue_share_pct": 40}]
        chart = build_chart(case["question"], rows, plan)
        assert chart["type"] == case["chart"], (case["question"], chart)
    try:
        audit_sql_plan("DELETE FROM t_order_sku_detail", {"start_time": "2026-01-01", "end_time_exclusive": "2026-02-01"})
    except ValueError:
        pass
    else:
        raise AssertionError("dangerous SQL was not rejected")

    ark_intent = normalize_analysis_intent(
        {"dimensions": ["shop"], "metrics": ["profit"], "order_metric": "profit", "wants_share": False}
    )
    assert ark_intent and ark_intent["dimensions"] == ["shop"]
    assert normalize_analysis_intent({"dimensions": ["DROP TABLE"], "metrics": ["revenue"]}) is None
    print(f"OK: {len(CASES)} natural-language analytics checks passed.")


if __name__ == "__main__":
    main()
