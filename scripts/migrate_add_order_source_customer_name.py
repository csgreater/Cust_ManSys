from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection, parse_database_url  # noqa: E402


def column_exists(cur, table_name: str, column_name: str) -> bool:
    cfg = parse_database_url()
    cur.execute(
        """
        SELECT COUNT(*) AS c
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %(schema)s
          AND TABLE_NAME = %(table)s
          AND COLUMN_NAME = %(column)s
        """,
        {"schema": cfg.database, "table": table_name, "column": column_name},
    )
    return cur.fetchone()["c"] > 0


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
            if not column_exists(cur, "t_order_sku_detail", "order_source"):
                cur.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD COLUMN order_source VARCHAR(32) NOT NULL DEFAULT '' COMMENT '订单来源'
                    AFTER sku_id
                    """
                )
                print("Added t_order_sku_detail.order_source")
            if not column_exists(cur, "t_order_sku_detail", "customer_name"):
                cur.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD COLUMN customer_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '客户名称'
                    AFTER customer_no
                    """
                )
                print("Added t_order_sku_detail.customer_name")
            if not index_exists(cur, "t_order_sku_detail", "idx_order_source_time"):
                cur.execute("ALTER TABLE t_order_sku_detail ADD INDEX idx_order_source_time (order_source, ship_time)")
                print("Added idx_order_source_time")

            if not column_exists(cur, "tmp_order_import", "order_source"):
                cur.execute(
                    """
                    ALTER TABLE tmp_order_import
                    ADD COLUMN order_source VARCHAR(32) NOT NULL DEFAULT ''
                    AFTER sku_id
                    """
                )
                print("Added tmp_order_import.order_source")
            if not column_exists(cur, "tmp_order_import", "customer_name"):
                cur.execute(
                    """
                    ALTER TABLE tmp_order_import
                    ADD COLUMN customer_name VARCHAR(64) NOT NULL DEFAULT ''
                    AFTER customer_no
                    """
                )
                print("Added tmp_order_import.customer_name")
    print("Migration complete.")


if __name__ == "__main__":
    main()
