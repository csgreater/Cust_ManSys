from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection


def add_district_column() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as exists_count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 't_order_sku_detail'
                  AND COLUMN_NAME = 'district'
                """
            )
            if cur.fetchone()["exists_count"] == 0:
                cur.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD COLUMN district VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'district/county'
                    AFTER city
                    """
                )
                print("Added district column to t_order_sku_detail")
            else:
                print("district column already exists in t_order_sku_detail")

            cur.execute(
                """
                SELECT COUNT(*) as exists_count
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'tmp_order_import'
                  AND COLUMN_NAME = 'district'
                """
            )
            if cur.fetchone()["exists_count"] == 0:
                cur.execute(
                    """
                    ALTER TABLE tmp_order_import
                    ADD COLUMN district VARCHAR(64) NOT NULL DEFAULT ''
                    AFTER city
                    """
                )
                print("Added district column to tmp_order_import")
            else:
                print("district column already exists in tmp_order_import")


if __name__ == "__main__":
    add_district_column()
    print("Migration completed successfully.")
