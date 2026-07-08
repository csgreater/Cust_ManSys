from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import connection, parse_database_url  # noqa: E402


REQUIRED_TABLES = {
    "t_order_sku_detail",
    "tmp_order_import",
    "t_import_log",
    "t_user",
    "t_role",
    "t_user_role",
    "t_role_data_scope",
}

REQUIRED_INDEXES = {
    "t_order_sku_detail": {
        "PRIMARY",
        "uk_order_sku_product_time",
        "idx_ship_time",
        "idx_product_no_time",
        "idx_sku_time",
        "idx_category_time",
        "idx_order_source_time",
        "idx_platform_shop_time",
        "idx_customer_time",
        "idx_logistics_no",
    },
    "tmp_order_import": {"PRIMARY", "idx_batch_no", "idx_batch_error", "idx_import_duplicate"},
    "t_import_log": {"PRIMARY", "batch_no", "idx_status_time", "idx_import_time"},
    "t_user": {"PRIMARY", "username", "idx_active_username"},
    "t_role": {"PRIMARY", "role_code"},
    "t_user_role": {"PRIMARY", "idx_role_id"},
    "t_role_data_scope": {"PRIMARY", "uk_role_scope", "idx_scope_lookup"},
}

REQUIRED_COLUMNS = {
    "t_order_sku_detail": {
        "id",
        "link_id",
        "sku_id",
        "order_source",
        "customer_no",
        "customer_name",
        "dept",
        "platform",
        "shop_name",
        "order_no",
        "original_order_no",
        "logistics_type",
        "logistics_no",
        "receiver_name",
        "receiver_address",
        "receiver_phone",
        "category",
        "product_name",
        "product_no",
        "unit",
        "qty",
        "share_receivable",
        "province",
        "city",
        "district",
        "ship_time",
        "cost",
        "express_fee",
        "logistics_fee",
        "freight",
        "aux_material",
        "share_cost",
        "profit",
        "create_time",
        "update_time",
        "is_deleted",
    },
    "tmp_order_import": {
        "id",
        "batch_no",
        "row_no",
        "link_id",
        "sku_id",
        "order_source",
        "customer_no",
        "customer_name",
        "dept",
        "platform",
        "shop_name",
        "order_no",
        "original_order_no",
        "logistics_type",
        "logistics_no",
        "receiver_name",
        "receiver_address",
        "receiver_phone",
        "category",
        "product_name",
        "product_no",
        "unit",
        "qty",
        "share_receivable",
        "province",
        "city",
        "district",
        "ship_time",
        "cost",
        "express_fee",
        "logistics_fee",
        "freight",
        "aux_material",
        "share_cost",
        "excel_profit",
        "profit",
        "error_message",
        "warning_message",
        "create_time",
    },
}

REQUIRED_COLUMN_LENGTHS = {
    "t_order_sku_detail": {
        "order_no": 128,
        "original_order_no": 512,
        "receiver_address": 512,
    },
    "tmp_order_import": {
        "order_no": 128,
        "original_order_no": 512,
        "receiver_address": 512,
    },
}


def main() -> None:
    cfg = parse_database_url()
    errors: list[str] = []
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT TABLE_NAME
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %(schema)s
                """,
                {"schema": cfg.database},
            )
            tables = {row["TABLE_NAME"] for row in cur.fetchall()}
            missing_tables = REQUIRED_TABLES - tables
            if missing_tables:
                errors.append(f"Missing tables: {', '.join(sorted(missing_tables))}")

            for table, required_indexes in REQUIRED_INDEXES.items():
                if table not in tables:
                    continue
                cur.execute(f"SHOW INDEX FROM `{table}`")
                indexes = {row["Key_name"] for row in cur.fetchall()}
                missing_indexes = required_indexes - indexes
                if missing_indexes:
                    errors.append(f"{table} missing indexes: {', '.join(sorted(missing_indexes))}")

            for table, required_columns in REQUIRED_COLUMNS.items():
                if table not in tables:
                    continue
                cur.execute(
                    """
                    SELECT COLUMN_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %(schema)s
                      AND TABLE_NAME = %(table)s
                    """,
                    {"schema": cfg.database, "table": table},
                )
                columns = {row["COLUMN_NAME"] for row in cur.fetchall()}
                missing_columns = required_columns - columns
                if missing_columns:
                    errors.append(f"{table} missing columns: {', '.join(sorted(missing_columns))}")

            for table, required_lengths in REQUIRED_COLUMN_LENGTHS.items():
                if table not in tables:
                    continue
                cur.execute(
                    """
                    SELECT COLUMN_NAME, CHARACTER_MAXIMUM_LENGTH
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %(schema)s
                      AND TABLE_NAME = %(table)s
                      AND COLUMN_NAME IN %(columns)s
                    """,
                    {"schema": cfg.database, "table": table, "columns": tuple(required_lengths)},
                )
                lengths = {row["COLUMN_NAME"]: row["CHARACTER_MAXIMUM_LENGTH"] for row in cur.fetchall()}
                for column, required_length in required_lengths.items():
                    actual_length = lengths.get(column)
                    if actual_length is None:
                        continue
                    if int(actual_length) < required_length:
                        errors.append(
                            f"{table}.{column} length {actual_length} is less than required {required_length}"
                        )

            cur.execute(
                """
                SELECT PARTITION_NAME
                FROM information_schema.PARTITIONS
                WHERE TABLE_SCHEMA = %(schema)s
                  AND TABLE_NAME = 't_order_sku_detail'
                  AND PARTITION_NAME IS NOT NULL
                ORDER BY PARTITION_ORDINAL_POSITION
                """,
                {"schema": cfg.database},
            )
            partitions = [row["PARTITION_NAME"] for row in cur.fetchall()]
            if not partitions:
                errors.append("t_order_sku_detail has no partitions")
            elif partitions[-1] != "pmax":
                errors.append("t_order_sku_detail should end with pmax partition")

            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM t_user u
                INNER JOIN t_user_role ur ON ur.user_id = u.id
                INNER JOIN t_role r ON r.id = ur.role_id
                WHERE u.username IN ('admin', 'importer', 'analyst', 'viewer')
                """
            )
            if cur.fetchone()["c"] < 4:
                errors.append("Seed users or roles are incomplete")

    if errors:
        print("Database readiness check FAILED:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"Database `{cfg.database}` readiness check passed.")


if __name__ == "__main__":
    main()
