from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import connection, parse_database_url  # noqa: E402
from app.security import hash_password  # noqa: E402


def month_iter(start_year: int, end_year: int):
    year = start_year
    month = 1
    while year <= end_year:
        current = date(year, month, 1)
        next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        yield current, next_month
        month += 1
        if month == 13:
            month = 1
            year += 1


def partition_sql() -> str:
    current_year = date.today().year
    start_year = min(2020, current_year - 3)
    end_year = current_year + 5
    parts = [
        f"PARTITION p{current:%Y%m} VALUES LESS THAN (TO_DAYS('{next_month:%Y-%m-%d}'))"
        for current, next_month in month_iter(start_year, end_year)
    ]
    parts.append("PARTITION pmax VALUES LESS THAN MAXVALUE")
    return ",\n  ".join(parts)


def create_database() -> None:
    cfg = parse_database_url()
    with connection(database="") as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )


def create_tables() -> None:
    parts = partition_sql()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS t_order_sku_detail (
                  id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'detail id',
                  link_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'product link id',
                  sku_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'sku id, optional',
                  order_source VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'order source, optional',
                  customer_no VARCHAR(32) NOT NULL COMMENT 'customer code',
                  customer_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'customer name',
                  dept VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'department',
                  platform VARCHAR(32) NOT NULL COMMENT 'platform channel',
                  shop_name VARCHAR(64) NOT NULL COMMENT 'shop name',
                  order_no VARCHAR(128) NOT NULL COMMENT 'order number',
                  original_order_no VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'original order number',
                  logistics_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'logistics type',
                  logistics_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'logistics number',
                  receiver_name VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'receiver name',
                  receiver_address VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'receiver address',
                  receiver_phone VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'receiver phone',
                  category VARCHAR(32) NOT NULL COMMENT 'product category',
                  product_name VARCHAR(255) NOT NULL COMMENT 'product name',
                  product_no VARCHAR(64) NOT NULL COMMENT 'product code',
                  unit VARCHAR(16) NOT NULL COMMENT 'unit',
                  qty DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT 'quantity',
                  share_receivable DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'allocated receivable',
                  province VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'province',
                  city VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'city',
                  district VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'district/county',
                  ship_time DATETIME NOT NULL COMMENT 'ship time',
                  cost DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'cost',
                  express_fee DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'express fee',
                  logistics_fee DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'logistics fee',
                  freight DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'freight',
                  aux_material DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'auxiliary material',
                  share_cost DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'allocated cost',
                  profit DECIMAL(12,2) GENERATED ALWAYS AS
                    (share_receivable - cost - freight - aux_material - share_cost) STORED COMMENT 'calculated profit',
                  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  is_deleted TINYINT NOT NULL DEFAULT 0,
                  PRIMARY KEY (id, ship_time),
                  KEY idx_order_sku_product_time (order_no, sku_id, product_no, ship_time),
                  KEY idx_ship_time (ship_time),
                  KEY idx_product_no_time (product_no, ship_time),
                  KEY idx_sku_time (sku_id, ship_time),
                  KEY idx_category_time (category, ship_time),
                  KEY idx_order_source_time (order_source, ship_time),
                  KEY idx_platform_shop_time (platform, shop_name, ship_time),
                  KEY idx_customer_time (customer_no, ship_time),
                  KEY idx_logistics_no (logistics_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='order sku detail'
                PARTITION BY RANGE (TO_DAYS(ship_time)) (
                  {parts}
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tmp_order_import (
                  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  batch_no VARCHAR(64) NOT NULL,
                  row_no INT NOT NULL,
                  link_id VARCHAR(64) NOT NULL DEFAULT '',
                  sku_id VARCHAR(64) NOT NULL DEFAULT '',
                  order_source VARCHAR(32) NOT NULL DEFAULT '',
                  customer_no VARCHAR(32) NOT NULL DEFAULT '',
                  customer_name VARCHAR(64) NOT NULL DEFAULT '',
                  dept VARCHAR(32) NOT NULL DEFAULT '',
                  platform VARCHAR(32) NOT NULL DEFAULT '',
                  shop_name VARCHAR(64) NOT NULL DEFAULT '',
                  order_no VARCHAR(128) NOT NULL DEFAULT '',
                  original_order_no VARCHAR(512) NOT NULL DEFAULT '',
                  logistics_type VARCHAR(32) NOT NULL DEFAULT '',
                  logistics_no VARCHAR(64) NOT NULL DEFAULT '',
                  receiver_name VARCHAR(32) NOT NULL DEFAULT '',
                  receiver_address VARCHAR(512) NOT NULL DEFAULT '',
                  receiver_phone VARCHAR(32) NOT NULL DEFAULT '',
                  category VARCHAR(32) NOT NULL DEFAULT '',
                  product_name VARCHAR(255) NOT NULL DEFAULT '',
                  product_no VARCHAR(64) NOT NULL DEFAULT '',
                  unit VARCHAR(16) NOT NULL DEFAULT '',
                  qty DECIMAL(10,2) NOT NULL DEFAULT 0,
                  share_receivable DECIMAL(12,2) NOT NULL DEFAULT 0,
                  province VARCHAR(32) NOT NULL DEFAULT '',
                  city VARCHAR(64) NOT NULL DEFAULT '',
                  district VARCHAR(64) NOT NULL DEFAULT '',
                  ship_time DATETIME NULL,
                  cost DECIMAL(12,2) NOT NULL DEFAULT 0,
                  express_fee DECIMAL(12,2) NOT NULL DEFAULT 0,
                  logistics_fee DECIMAL(12,2) NOT NULL DEFAULT 0,
                  freight DECIMAL(12,2) NOT NULL DEFAULT 0,
                  aux_material DECIMAL(12,2) NOT NULL DEFAULT 0,
                  share_cost DECIMAL(12,2) NOT NULL DEFAULT 0,
                  excel_profit DECIMAL(12,2) NULL,
                  profit DECIMAL(12,2) NOT NULL DEFAULT 0,
                  error_message VARCHAR(1000) NOT NULL DEFAULT '',
                  warning_message VARCHAR(1000) NOT NULL DEFAULT '',
                  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  KEY idx_batch_no (batch_no),
                  KEY idx_batch_error (batch_no, error_message(100)),
                  KEY idx_import_duplicate (batch_no, order_no, ship_time, sku_id, product_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='order import staging'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_import_log (
                  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  batch_no VARCHAR(64) NOT NULL UNIQUE,
                  import_user VARCHAR(32) NOT NULL,
                  file_name VARCHAR(255) NOT NULL DEFAULT '',
                  total_rows INT NOT NULL DEFAULT 0,
                  success_rows INT NOT NULL DEFAULT 0,
                  fail_rows INT NOT NULL DEFAULT 0,
                  duplicate_rows INT NOT NULL DEFAULT 0,
                  file_hash VARCHAR(64) NOT NULL DEFAULT '',
                  status VARCHAR(32) NOT NULL DEFAULT 'validated',
                  import_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  remark VARCHAR(500) NOT NULL DEFAULT '',
                  KEY idx_file_hash_status (file_hash, status),
                  KEY idx_status_time (status, import_time),
                  KEY idx_import_time (import_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='import log'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_user (
                  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(32) NOT NULL UNIQUE,
                  display_name VARCHAR(64) NOT NULL,
                  password_hash VARCHAR(255) NOT NULL,
                  is_active TINYINT NOT NULL DEFAULT 1,
                  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  KEY idx_active_username (is_active, username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='system user'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_role (
                  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  role_code VARCHAR(32) NOT NULL UNIQUE,
                  role_name VARCHAR(64) NOT NULL,
                  permissions VARCHAR(255) NOT NULL DEFAULT ''
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='system role'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_user_role (
                  user_id BIGINT NOT NULL,
                  role_id BIGINT NOT NULL,
                  PRIMARY KEY (user_id, role_id),
                  KEY idx_role_id (role_id),
                  CONSTRAINT fk_user_role_user FOREIGN KEY (user_id) REFERENCES t_user(id),
                  CONSTRAINT fk_user_role_role FOREIGN KEY (role_id) REFERENCES t_role(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='user role relation'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_role_data_scope (
                  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  role_id BIGINT NOT NULL,
                  scope_type VARCHAR(16) NOT NULL,
                  scope_value VARCHAR(64) NOT NULL,
                  UNIQUE KEY uk_role_scope (role_id, scope_type, scope_value),
                  KEY idx_scope_lookup (scope_type, scope_value),
                  CONSTRAINT fk_scope_role FOREIGN KEY (role_id) REFERENCES t_role(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='role data scope'
                """
            )


def seed_data() -> None:
    roles = [
        ("admin", "管理员", "admin,view,import,analytics,export,settings"),
        ("importer", "导入员", "view,import"),
        ("analyst", "分析员", "view,analytics,export"),
        ("viewer", "只读用户", "view"),
    ]
    users = [
        ("admin", "系统管理员", settings.admin_password, "admin"),
        ("importer", "导入员", settings.importer_password, "importer"),
        ("analyst", "分析员", settings.analyst_password, "analyst"),
        ("viewer", "只读用户", settings.viewer_password, "viewer"),
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            for code, name, permissions in roles:
                cur.execute(
                    """
                    INSERT INTO t_role (role_code, role_name, permissions)
                    VALUES (%(code)s, %(name)s, %(permissions)s)
                    ON DUPLICATE KEY UPDATE role_name = VALUES(role_name), permissions = VALUES(permissions)
                    """,
                    {"code": code, "name": name, "permissions": permissions},
                )
            cur.execute("SELECT id, role_code FROM t_role")
            role_ids = {row["role_code"]: row["id"] for row in cur.fetchall()}

            for username, display_name, password, role_code in users:
                cur.execute("SELECT id FROM t_user WHERE username = %(username)s", {"username": username})
                row = cur.fetchone()
                if row:
                    user_id = row["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO t_user (username, display_name, password_hash)
                        VALUES (%(username)s, %(display_name)s, %(password_hash)s)
                        """,
                        {
                            "username": username,
                            "display_name": display_name,
                            "password_hash": hash_password(password),
                        },
                    )
                    user_id = cur.lastrowid
                cur.execute(
                    """
                    INSERT IGNORE INTO t_user_role (user_id, role_id)
                    VALUES (%(user_id)s, %(role_id)s)
                    """,
                    {"user_id": user_id, "role_id": role_ids[role_code]},
                )

            for role_code in ("admin", "importer", "analyst"):
                role_id = role_ids[role_code]
                for scope_type in ("dept", "platform", "shop"):
                    cur.execute(
                        """
                        INSERT IGNORE INTO t_role_data_scope (role_id, scope_type, scope_value)
                        VALUES (%(role_id)s, %(scope_type)s, '*')
                        """,
                        {"role_id": role_id, "scope_type": scope_type},
                    )


def main() -> None:
    create_database()
    create_tables()
    seed_data()
    cfg = parse_database_url()
    print(f"Initialized database `{cfg.database}`.")
    print("Seed users: admin/importer/analyst/viewer. Passwords come from .env or defaults.")


if __name__ == "__main__":
    main()
