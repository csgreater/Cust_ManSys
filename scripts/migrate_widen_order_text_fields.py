from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


TARGET_LENGTHS = {
    "order_no": 128,
    "original_order_no": 512,
    "receiver_address": 512,
}


def column_length(table: str, column: str) -> int | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH AS length
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %(table)s
                  AND COLUMN_NAME = %(column)s
                """,
                {"table": table, "column": column},
            )
            row = cur.fetchone()
            return int(row["length"]) if row and row["length"] is not None else None


def widen_column(table: str, column: str, length: int) -> None:
    current = column_length(table, column)
    if current is None:
        print(f"{table}.{column} does not exist, skipped")
        return
    if current >= length:
        print(f"{table}.{column} already length {current}")
        return
    with connection() as conn:
        with conn.cursor() as cur:
            comment = {
                "order_no": "order number",
                "original_order_no": "original order number",
                "receiver_address": "receiver address",
            }[column]
            cur.execute(
                f"""
                ALTER TABLE `{table}`
                MODIFY COLUMN `{column}` VARCHAR({length}) NOT NULL DEFAULT '' COMMENT '{comment}'
                """
            )
    print(f"Widened {table}.{column} from {current} to {length}")


def main() -> None:
    for table in ("t_order_sku_detail", "tmp_order_import"):
        for column, length in TARGET_LENGTHS.items():
            widen_column(table, column, length)
    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
