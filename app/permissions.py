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
            SELECT u.id, u.username, u.display_name, u.is_active,
                   r.id AS role_id, r.role_code, r.role_name, r.permissions,
                   s.scope_type, s.scope_value
            FROM t_user u
            LEFT JOIN t_user_role ur ON ur.user_id = u.id
            LEFT JOIN t_role r ON r.id = ur.role_id
            LEFT JOIN t_role_data_scope s ON s.role_id = r.id
            WHERE u.id = %(user_id)s AND u.is_active = 1
            ORDER BY r.id, s.scope_type, s.scope_value
            """,
            {"user_id": user_id},
        )
        rows = list(cur.fetchall())
    if not rows:
        return None

    first = rows[0]
    user: dict[str, Any] = {
        "id": first["id"],
        "username": first["username"],
        "display_name": first["display_name"],
        "is_active": first["is_active"],
    }
    roles_by_id: dict[int, dict[str, Any]] = {}
    scopes = {"dept": set(), "platform": set(), "shop": set()}
    all_scopes = {"dept": False, "platform": False, "shop": False}
    for row in rows:
        role_id = row.get("role_id")
        if role_id is not None and role_id not in roles_by_id:
            roles_by_id[role_id] = {
                "id": role_id,
                "role_code": row["role_code"],
                "role_name": row["role_name"],
                "permissions": row["permissions"],
            }
        scope_type = row.get("scope_type")
        value = row.get("scope_value")
        if scope_type in scopes and value:
            if value == "*":
                all_scopes[scope_type] = True
            else:
                scopes[scope_type].add(value)

    roles = list(roles_by_id.values())

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
