"""Add workbench storage and import provenance; never rewrite existing business rows."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection
from app.workbench_store import create_workbench_tables


def migrate(conn) -> None:
    create_workbench_tables(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='t_order_sku_detail'")
        columns = {r["COLUMN_NAME"] for r in cur.fetchall()}
        for name, ddl in (
            ("source_batch_no", "VARCHAR(64) NOT NULL DEFAULT ''"),
            ("source_row_no", "INT NULL"),
        ):
            if name not in columns:
                cur.execute(f"ALTER TABLE t_order_sku_detail ADD COLUMN {name} {ddl}")
        cur.execute("SHOW INDEX FROM t_order_sku_detail")
        indexes = {r["Key_name"] for r in cur.fetchall()}
        if "idx_source_batch_row" not in indexes:
            cur.execute("ALTER TABLE t_order_sku_detail ADD INDEX idx_source_batch_row (source_batch_no, source_row_no)")


def main():
    with connection() as conn:
        migrate(conn)
    print("Anomaly workbench schema is ready; existing order values were not rewritten.")


if __name__ == "__main__":
    main()
