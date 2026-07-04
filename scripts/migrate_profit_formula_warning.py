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


def main() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                ALTER TABLE t_order_sku_detail
                MODIFY COLUMN profit DECIMAL(12,2)
                GENERATED ALWAYS AS
                  (share_receivable - cost - freight - aux_material - share_cost)
                STORED COMMENT '系统计算利润'
                """
            )
            print("Updated t_order_sku_detail.profit formula")

            if not column_exists(cur, "tmp_order_import", "warning_message"):
                cur.execute(
                    """
                    ALTER TABLE tmp_order_import
                    ADD COLUMN warning_message VARCHAR(1000) NOT NULL DEFAULT ''
                    AFTER error_message
                    """
                )
                print("Added tmp_order_import.warning_message")
    print("Migration complete.")


if __name__ == "__main__":
    main()
