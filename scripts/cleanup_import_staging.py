from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean old import staging rows.")
    parser.add_argument("--days", type=int, default=7, help="Clean committed/failed batches older than this many days.")
    parser.add_argument("--stale-hours", type=int, default=6, help="Mark processing batches older than this many hours as failed.")
    args = parser.parse_args()

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE t_import_log
                SET status = 'failed',
                    remark = '导入任务超时未更新，已由清理脚本关闭'
                WHERE status = 'processing'
                  AND import_time < DATE_SUB(NOW(), INTERVAL %(hours)s HOUR)
                """,
                {"hours": args.stale_hours},
            )
            stale = cur.rowcount

            cur.execute(
                """
                DELETE t
                FROM tmp_order_import t
                INNER JOIN t_import_log l ON l.batch_no = t.batch_no
                WHERE l.status IN ('committed', 'failed')
                  AND l.import_time < DATE_SUB(NOW(), INTERVAL %(days)s DAY)
                """,
                {"days": args.days},
            )
            deleted = cur.rowcount

    print(f"Marked stale processing batches: {stale}")
    print(f"Deleted staging rows: {deleted}")


if __name__ == "__main__":
    main()
