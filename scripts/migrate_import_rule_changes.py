from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) AS exists_count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %(table)s
          AND COLUMN_NAME = %(column)s
        """,
        {"table": table, "column": column},
    )
    return cur.fetchone()["exists_count"] > 0


def index_exists(cur, table: str, index_name: str) -> bool:
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
    with connection() as conn:
        with conn.cursor() as cur:
            if not column_exists(cur, "t_import_log", "file_hash"):
                cur.execute(
                    """
                    ALTER TABLE t_import_log
                    ADD COLUMN file_hash VARCHAR(64) NOT NULL DEFAULT ''
                    AFTER duplicate_rows
                    """
                )
                print("Added t_import_log.file_hash")
            else:
                print("t_import_log.file_hash already exists")

            if not index_exists(cur, "t_import_log", "idx_file_hash_status"):
                cur.execute("ALTER TABLE t_import_log ADD INDEX idx_file_hash_status (file_hash, status)")
                print("Added t_import_log.idx_file_hash_status")
            else:
                print("t_import_log.idx_file_hash_status already exists")

            if index_exists(cur, "t_order_sku_detail", "uk_order_sku_product_time"):
                cur.execute("ALTER TABLE t_order_sku_detail DROP INDEX uk_order_sku_product_time")
                print("Dropped t_order_sku_detail.uk_order_sku_product_time")
            else:
                print("t_order_sku_detail.uk_order_sku_product_time already absent")

            if not index_exists(cur, "t_order_sku_detail", "idx_order_sku_product_time"):
                cur.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD INDEX idx_order_sku_product_time (order_no, sku_id, product_no, ship_time)
                    """
                )
                print("Added t_order_sku_detail.idx_order_sku_product_time")
            else:
                print("t_order_sku_detail.idx_order_sku_product_time already exists")
    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
