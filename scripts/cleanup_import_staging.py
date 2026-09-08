from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection
from app.import_lifecycle import recover_stale_batch
from fastapi import HTTPException


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean old import staging rows.")
    parser.add_argument("--days", type=int, default=7, help="Clean committed/failed batches older than this many days.")
    parser.add_argument("--stale-hours", type=int, default=6, help="Mark processing batches older than this many hours as failed.")
    args = parser.parse_args()
    if args.days < 1 or args.stale_hours < 1:
        parser.error("days and stale-hours must be positive")

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT batch_no FROM t_import_log
                WHERE status = 'processing'
                  AND import_time < DATE_SUB(NOW(), INTERVAL %(hours)s HOUR)
                """,
                {"hours": args.stale_hours},
            )
            candidates = list(cur.fetchall())

    stale = 0
    for batch in candidates:
        try:
            with connection() as conn:
                recover_stale_batch(conn, {"permissions": {"admin"}}, batch["batch_no"],
                                    min_idle_seconds=args.stale_hours * 3600)
            stale += 1
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise

    with connection() as conn:
        with conn.cursor() as cur:
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
