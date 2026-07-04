from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection, parse_database_url  # noqa: E402


def index_exists(cur, table_name: str, index_name: str) -> bool:
    cfg = parse_database_url()
    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %(schema)s
          AND TABLE_NAME = %(table)s
          AND INDEX_NAME = %(index_name)s
        """,
        {"schema": cfg.database, "table": table_name, "index_name": index_name},
    )
    return cur.fetchone()["c"] > 0


def main() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            if index_exists(cur, "t_order_sku_detail", "uk_order_sku_time"):
                cur.execute("ALTER TABLE t_order_sku_detail DROP INDEX uk_order_sku_time")
                print("Dropped uk_order_sku_time")
            if not index_exists(cur, "t_order_sku_detail", "uk_order_sku_product_time"):
                cur.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD UNIQUE KEY uk_order_sku_product_time (order_no, sku_id, product_no, ship_time)
                    """
                )
                print("Added uk_order_sku_product_time")
    print("Migration complete.")


if __name__ == "__main__":
    main()
