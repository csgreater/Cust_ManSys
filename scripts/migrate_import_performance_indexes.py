from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


def index_exists(table: str, index_name: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS exists_count
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %(table)s
                  AND INDEX_NAME = %(index_name)s
                """,
                {"table": table, "index_name": index_name},
            )
            return cur.fetchone()["exists_count"] > 0


def main() -> None:
    if index_exists("tmp_order_import", "idx_import_duplicate"):
        print("tmp_order_import.idx_import_duplicate already exists")
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE tmp_order_import
                ADD INDEX idx_import_duplicate (batch_no, order_no, ship_time, sku_id, product_no)
                """
            )
    print("Added tmp_order_import.idx_import_duplicate")


if __name__ == "__main__":
    main()
