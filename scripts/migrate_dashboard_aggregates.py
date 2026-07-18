from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.analytics_aggregates import create_dashboard_tables, refresh_dashboard_months  # noqa: E402
from app.db import connection  # noqa: E402


def main() -> None:
    started = time.perf_counter()
    with connection() as conn:
        create_dashboard_tables(conn)
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
        refreshed = refresh_dashboard_months(conn, months)
    elapsed = time.perf_counter() - started
    print(
        f"Dashboard aggregate migration complete: months={len(refreshed)}, "
        f"elapsed_seconds={elapsed:.2f}"
    )


if __name__ == "__main__":
    main()
