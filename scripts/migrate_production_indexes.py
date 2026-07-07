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


def add_index(cur, table: str, index_name: str, definition: str) -> None:
    if not index_exists(cur, table, index_name):
        cur.execute(f"ALTER TABLE {table} ADD INDEX {index_name} {definition}")
        print(f"Added {table}.{index_name}")


def main() -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            add_index(cur, "t_import_log", "idx_status_time", "(status, import_time)")
            add_index(cur, "t_import_log", "idx_import_time", "(import_time)")
            add_index(cur, "t_user", "idx_active_username", "(is_active, username)")
            add_index(cur, "t_user_role", "idx_role_id", "(role_id)")
            add_index(cur, "t_role_data_scope", "idx_scope_lookup", "(scope_type, scope_value)")
    print("Production indexes migration complete.")


if __name__ == "__main__":
    main()
