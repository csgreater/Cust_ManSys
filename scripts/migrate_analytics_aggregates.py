from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.analytics_aggregates import create_product_monthly_table, refresh_product_months  # noqa: E402
from app.db import connection  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    with connection() as conn:
        create_product_monthly_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT DATE_FORMAT(ship_time, '%Y-%m-01') AS stat_month
                FROM t_order_sku_detail
                WHERE ship_time >= '2000-01-01'
                ORDER BY stat_month
                """
            )
            months = [row["stat_month"] for row in cur.fetchall()]
        refreshed = refresh_product_months(conn, months)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM agg_product_monthly")
            aggregate_rows = cur.fetchone()["c"]
    elapsed = time.perf_counter() - started
    print(
        f"Analytics aggregate migration complete: months={len(refreshed)}, "
        f"rows={aggregate_rows}, elapsed_seconds={elapsed:.2f}"
    )


if __name__ == "__main__":
    main()
