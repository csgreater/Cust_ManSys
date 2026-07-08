from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


def column_exists(table: str, column: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS exists_count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %(table)s
                  AND COLUMN_NAME = %(column)s
                """,
                {"table": table, "column": column},
            )
            return cur.fetchone()["exists_count"] > 0


def add_column_if_missing(table: str, after_column: str) -> None:
    if column_exists(table, "receiver_address"):
        print(f"receiver_address column already exists in {table}")
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                ALTER TABLE `{table}`
                ADD COLUMN receiver_address VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'receiver address'
                AFTER `{after_column}`
                """
            )
    print(f"Added receiver_address column to {table}")


def main() -> None:
    add_column_if_missing("t_order_sku_detail", "receiver_name")
    add_column_if_missing("tmp_order_import", "receiver_name")
    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
