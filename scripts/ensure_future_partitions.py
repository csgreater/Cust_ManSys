from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection, parse_database_url  # noqa: E402


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def main(months_ahead: int = 6) -> None:
    cfg = parse_database_url()
    today_month = date.today().replace(day=1)
    required = []
    for offset in range(months_ahead + 1):
        current = add_months(today_month, offset)
        next_month = add_months(current, 1)
        required.append((f"p{current:%Y%m}", next_month))

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT PARTITION_NAME
                FROM information_schema.PARTITIONS
                WHERE TABLE_SCHEMA = %(schema)s
                  AND TABLE_NAME = 't_order_sku_detail'
                  AND PARTITION_NAME IS NOT NULL
                """,
                {"schema": cfg.database},
            )
            existing = {row["PARTITION_NAME"] for row in cur.fetchall()}
            missing = [(name, boundary) for name, boundary in required if name not in existing]
            if not missing:
                print("Future partitions already exist.")
                return

            partition_defs = ",\n  ".join(
                f"PARTITION {name} VALUES LESS THAN (TO_DAYS('{boundary:%Y-%m-%d}'))"
                for name, boundary in missing
            )
            sql = f"""
            ALTER TABLE t_order_sku_detail
            REORGANIZE PARTITION pmax INTO (
              {partition_defs},
              PARTITION pmax VALUES LESS THAN MAXVALUE
            )
            """
            cur.execute(sql)
            print("Added partitions: " + ", ".join(name for name, _ in missing))


if __name__ == "__main__":
    main()
