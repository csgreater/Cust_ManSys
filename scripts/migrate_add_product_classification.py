"""Add the optional product-classification field to existing databases."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connection


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def index_exists(cursor, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (table_name, index_name),
    )
    return cursor.fetchone() is not None


def main() -> None:
    with connection() as conn:
        with conn.cursor() as cursor:
            if not column_exists(cursor, "t_order_sku_detail", "product_classification"):
                cursor.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD COLUMN product_classification VARCHAR(64) NOT NULL DEFAULT ''
                    COMMENT 'product classification' AFTER category
                    """
                )
                print("Added t_order_sku_detail.product_classification")

            if not column_exists(cursor, "tmp_order_import", "product_classification"):
                cursor.execute(
                    """
                    ALTER TABLE tmp_order_import
                    ADD COLUMN product_classification VARCHAR(64) NOT NULL DEFAULT ''
                    COMMENT 'product classification' AFTER category
                    """
                )
                print("Added tmp_order_import.product_classification")

            if not index_exists(cursor, "t_order_sku_detail", "idx_product_classification_time"):
                cursor.execute(
                    """
                    ALTER TABLE t_order_sku_detail
                    ADD KEY idx_product_classification_time (product_classification, ship_time)
                    """
                )
                print("Added idx_product_classification_time")
    print("Product-classification migration completed.")


if __name__ == "__main__":
    main()
