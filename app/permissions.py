from __future__ import annotations

from typing import Any


SCOPE_FIELDS = {
    "dept": "dept",
    "platform": "platform",
    "shop": "shop_name",
}


def load_user_context(conn, user_id: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, username, display_name, is_active
            FROM t_user
            WHERE id = %(user_id)s AND is_active = 1
            """,
            {"user_id": user_id},
        )
        user = cur.fetchone()
        if not user:
            return None

        cur.execute(
            """
            SELECT r.id, r.role_code, r.role_name, r.permissions
            FROM t_role r
            INNER JOIN t_user_role ur ON ur.role_id = r.id
            WHERE ur.user_id = %(user_id)s
            """,
            {"user_id": user_id},
        )
        roles = list(cur.fetchall())
        role_ids = [role["id"] for role in roles]
        scopes = {"dept": set(), "platform": set(), "shop": set()}
        all_scopes = {"dept": False, "platform": False, "shop": False}
        if role_ids:
            placeholders = ",".join(["%s"] * len(role_ids))
            cur.execute(
                f"""
                SELECT scope_type, scope_value
                FROM t_role_data_scope
                WHERE role_id IN ({placeholders})
                """,
                role_ids,
            )
            for row in cur.fetchall():
                scope_type = row["scope_type"]
                value = row["scope_value"]
                if scope_type in scopes:
                    if value == "*":
                        all_scopes[scope_type] = True
                    else:
                        scopes[scope_type].add(value)

        permissions: set[str] = set()
        role_codes = set()
        for role in roles:
            role_codes.add(role["role_code"])
            permissions.update(p.strip() for p in (role["permissions"] or "").split(",") if p.strip())

        if "admin" in role_codes:
            permissions.add("admin")
            for key in all_scopes:
                all_scopes[key] = True

        user["roles"] = roles
        user["role_codes"] = role_codes
        user["permissions"] = permissions
        user["scopes"] = {k: sorted(v) for k, v in scopes.items()}
        user["all_scopes"] = all_scopes
        return user


def has_permission(user: dict[str, Any], permission: str) -> bool:
    return "admin" in user["permissions"] or permission in user["permissions"]


def scope_clause(
    user: dict[str, Any],
    params: dict[str, Any],
    alias: str = "o",
    field_prefix: str = "scope",
) -> str:
    clauses: list[str] = []
    for scope_type, field in SCOPE_FIELDS.items():
        if user["all_scopes"].get(scope_type):
            continue
        values = user["scopes"].get(scope_type) or []
        if not values:
            return " AND 1 = 0"
        keys = []
        for index, value in enumerate(values):
            key = f"{field_prefix}_{scope_type}_{index}"
            params[key] = value
            keys.append(f"%({key})s")
        clauses.append(f" AND {alias}.{field} IN ({','.join(keys)})")
    return "".join(clauses)


def requested_scope_filters(params: dict[str, Any], alias: str = "o") -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    for key, field in (("dept", "dept"), ("platform", "platform"), ("shop_name", "shop_name")):
        value = params.get(key)
        if value:
            clauses.append(f" AND {alias}.{field} = %({key})s")
    return "".join(clauses), params
