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
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        yield current, next_month
        month += 1
        if month == 13:
            month = 1
            year += 1


def partition_sql() -> str:
    current_year = date.today().year
    start_year = min(2020, current_year - 3)
    end_year = current_year + 5
    parts = []
    for current, next_month in month_iter(start_year, end_year):
        parts.append(
            f"PARTITION p{current:%Y%m} VALUES LESS THAN (TO_DAYS('{next_month:%Y-%m-%d}'))"
        )
    parts.append("PARTITION pmax VALUES LESS THAN MAXVALUE")
    return ",\n  ".join(parts)


def create_database() -> None:
    cfg = parse_database_url()
    with connection(database="") as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )


def create_tables() -> None:
    parts = partition_sql()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS t_order_sku_detail (
                  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '明细ID',
                  link_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '商品链接Id',
                  sku_id VARCHAR(64) NOT NULL COMMENT '商品链接SkuId',
                  order_source VARCHAR(32) NOT NULL DEFAULT '' COMMENT '订单来源',
                  customer_no VARCHAR(32) NOT NULL COMMENT '客户编号',
                  customer_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT '客户名称',
                  dept VARCHAR(32) NOT NULL DEFAULT '' COMMENT '部门',
                  platform VARCHAR(32) NOT NULL COMMENT '平台渠道',
                  shop_name VARCHAR(64) NOT NULL COMMENT '店铺',
                  order_no VARCHAR(64) NOT NULL COMMENT '订单编号',
                  original_order_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '原始单号',
                  logistics_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT '物流方式',
                  logistics_no VARCHAR(64) NOT NULL DEFAULT '' COMMENT '物流单号',
                  receiver_name VARCHAR(32) NOT NULL DEFAULT '' COMMENT '收货人',
                  receiver_phone VARCHAR(32) NOT NULL DEFAULT '' COMMENT '电话',
                  category VARCHAR(32) NOT NULL COMMENT '大类',
                  product_name VARCHAR(255) NOT NULL COMMENT '产品名称',
                  product_no VARCHAR(64) NOT NULL COMMENT '货品编号',
                  unit VARCHAR(16) NOT NULL COMMENT '单位',
                  qty DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '数量',
                  share_receivable DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '应收合计分摊',
                  province VARCHAR(32) NOT NULL DEFAULT '' COMMENT '州省',
                  city VARCHAR(64) NOT NULL DEFAULT '' COMMENT '区市',
                  ship_time DATETIME NOT NULL COMMENT '发货时间',
                  cost DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '成本',
                  express_fee DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '快递费',
                  logistics_fee DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '物流费',
                  freight DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '运费',
                  aux_material DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '辅料',
                  share_cost DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '分摊费用',
                  profit DECIMAL(12,2) GENERATED ALWAYS AS
                    (share_receivable - cost - freight - aux_material - share_cost) STORED COMMENT '系统计算利润',
                  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  is_deleted TINYINT NOT NULL DEFAULT 0,
                  PRIMARY KEY (id, ship_time),
                  UNIQUE KEY uk_order_sku_product_time (order_no, sku_id, product_no, ship_time),
                  KEY idx_ship_time (ship_time),
                  KEY idx_product_no_time (product_no, ship_time),
                  KEY idx_sku_time (sku_id, ship_time),
                  KEY idx_category_time (category, ship_time),
                  KEY idx_order_source_time (order_source, ship_time),
                  KEY idx_platform_shop_time (platform, shop_name, ship_time),
                  KEY idx_customer_time (customer_no, ship_time),
                  KEY idx_logistics_no (logistics_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='订单SKU明细表'
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
                  order_no VARCHAR(64) NOT NULL DEFAULT '',
                  original_order_no VARCHAR(64) NOT NULL DEFAULT '',
                  logistics_type VARCHAR(32) NOT NULL DEFAULT '',
                  logistics_no VARCHAR(64) NOT NULL DEFAULT '',
                  receiver_name VARCHAR(32) NOT NULL DEFAULT '',
                  receiver_phone VARCHAR(32) NOT NULL DEFAULT '',
                  category VARCHAR(32) NOT NULL DEFAULT '',
                  product_name VARCHAR(255) NOT NULL DEFAULT '',
                  product_no VARCHAR(64) NOT NULL DEFAULT '',
                  unit VARCHAR(16) NOT NULL DEFAULT '',
                  qty DECIMAL(10,2) NOT NULL DEFAULT 0,
                  share_receivable DECIMAL(12,2) NOT NULL DEFAULT 0,
                  province VARCHAR(32) NOT NULL DEFAULT '',
                  city VARCHAR(64) NOT NULL DEFAULT '',
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
                  KEY idx_batch_error (batch_no, error_message(100))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='订单导入暂存表'
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
                  status VARCHAR(32) NOT NULL DEFAULT 'validated',
                  import_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  remark VARCHAR(500) NOT NULL DEFAULT ''
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='导入日志表'
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
                  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS t_user_role (
                  user_id BIGINT NOT NULL,
                  role_id BIGINT NOT NULL,
                  PRIMARY KEY (user_id, role_id),
                  CONSTRAINT fk_user_role_user FOREIGN KEY (user_id) REFERENCES t_user(id),
                  CONSTRAINT fk_user_role_role FOREIGN KEY (role_id) REFERENCES t_role(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
                  CONSTRAINT fk_scope_role FOREIGN KEY (role_id) REFERENCES t_role(id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
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
    print("Seed users: admin/importer/analyst/viewer. Passwords come from .env or .env.example defaults.")


if __name__ == "__main__":
    main()
