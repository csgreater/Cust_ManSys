"""Persistent, immutable reports and per-user exception review decisions."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.permissions import has_permission


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default)


def digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def capture_scope(user: dict, filters: dict) -> dict:
    result = {}
    for key, field in (("dept", "dept"), ("platform", "platform"), ("shop", "shop_name")):
        unrestricted = bool(user.get("all_scopes", {}).get(key))
        values = set(user.get("scopes", {}).get(key, []))
        requested = filters.get(field)
        if requested:
            values = {requested} if unrestricted else values.intersection({requested})
            unrestricted = False
        result[key] = {"all": unrestricted, "values": sorted(values) if not unrestricted else []}
    return result


def authorize_report(user: dict, record: dict) -> None:
    if int(record["owner_id"]) != int(user["id"]):
        raise PermissionError("报告不属于当前账号")
    if any(not has_permission(user, p) for p in record.get("required_permissions", ["analytics"])):
        raise PermissionError("当前权限已不再覆盖报告内容")
    for key in ("dept", "platform", "shop"):
        saved = record["access"][key]
        if user.get("all_scopes", {}).get(key):
            continue
        current = set(user.get("scopes", {}).get(key, []))
        if saved["all"] or not set(saved["values"]).issubset(current):
            raise PermissionError("当前数据范围已不再覆盖报告，请按现有权限重新生成")


def merge_reviews(rows: list[dict], reviews: list[dict]) -> list[dict]:
    by_id = {r["exception_id"]: r for r in reviews}
    result = []
    for row in rows:
        review = by_id.get(row["id"])
        matches = review and review["evidence_hash"] == row["evidence_hash"]
        result.append({**row, "status": review["status"] if matches else "pending",
                       "note": review["note"] if matches else "", "reopened": bool(review and not matches),
                       "reviewed_at": review.get("updated_at") if matches else None})
    return result


def create_workbench_tables(conn) -> None:
    statements = [
        """CREATE TABLE IF NOT EXISTS t_workbench_rules (
          id INT NOT NULL PRIMARY KEY, rules_json TEXT NOT NULL, version VARCHAR(64) NOT NULL,
          updated_by BIGINT NOT NULL, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS t_exception_review (
          owner_id BIGINT NOT NULL, exception_id VARCHAR(64) NOT NULL,
          evidence_hash VARCHAR(64) NOT NULL, status VARCHAR(16) NOT NULL, note TEXT NOT NULL,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (owner_id, exception_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS t_analysis_report (
          id VARCHAR(36) NOT NULL PRIMARY KEY, owner_id BIGINT NOT NULL,
          series_key CHAR(64) NOT NULL, version INT NOT NULL, title VARCHAR(200) NOT NULL,
          report_type VARCHAR(16) NOT NULL, filters_json TEXT NOT NULL,
          access_json TEXT NOT NULL, permissions_json TEXT NOT NULL, body_json LONGTEXT NOT NULL,
          data_version VARCHAR(64) NOT NULL, rules_version VARCHAR(64) NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE KEY uk_report_version (series_key, version),
          KEY idx_report_owner (owner_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]
    with conn.cursor() as cur:
        for sql in statements:
            cur.execute(sql)


def load_rules(conn, default_rules: dict) -> tuple[dict, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT rules_json, version FROM t_workbench_rules WHERE id = 1")
        row = cur.fetchone()
    return (json.loads(row["rules_json"]), row["version"]) if row else (dict(default_rules), digest(default_rules))


def save_rules(conn, rules: dict, owner_id: int) -> str:
    version = digest(rules)
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO t_workbench_rules (id,rules_json,version,updated_by)
          VALUES (1,%(rules)s,%(version)s,%(owner)s)
          ON DUPLICATE KEY UPDATE rules_json=VALUES(rules_json),version=VALUES(version),
          updated_by=VALUES(updated_by),updated_at=NOW()""",
                    {"rules": canonical_json(rules), "version": version, "owner": owner_id})
    return version


def load_reviews(conn, owner_id: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT exception_id,evidence_hash,status,note,updated_at FROM t_exception_review WHERE owner_id=%(owner)s", {"owner": owner_id})
        return list(cur.fetchall())


def save_review(conn, owner_id: int, row: dict, status: str, note: str) -> None:
    if status not in {"pending", "confirmed", "dismissed"}:
        raise ValueError("无效核查状态")
    if len(note) > 2000:
        raise ValueError("核查备注不能超过 2000 字")
    if status == "dismissed" and not note.strip():
        raise ValueError("排除异常时请填写核查理由")
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO t_exception_review (owner_id,exception_id,evidence_hash,status,note)
          VALUES (%(owner)s,%(id)s,%(hash)s,%(status)s,%(note)s)
          ON DUPLICATE KEY UPDATE evidence_hash=VALUES(evidence_hash),status=VALUES(status),
          note=VALUES(note),updated_at=NOW()""",
                    {"owner": owner_id, "id": row["id"], "hash": row["evidence_hash"], "status": status, "note": note.strip()})


def decode_report(row: dict, *, with_body: bool = True) -> dict:
    result = {k: row[k] for k in ("id", "owner_id", "version", "title", "report_type", "created_at", "data_version", "rules_version")}
    result.update(filters=json.loads(row["filters_json"]), access=json.loads(row["access_json"]),
                  required_permissions=json.loads(row["permissions_json"]))
    if with_body:
        result["body"] = json.loads(row["body_json"])
    return result


def list_reports(conn, user: dict) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("""SELECT id,owner_id,version,title,report_type,created_at,data_version,rules_version,
          filters_json,access_json,permissions_json FROM t_analysis_report
          WHERE owner_id=%(owner)s ORDER BY created_at DESC,version DESC,id DESC""", {"owner": user["id"]})
        rows = list(cur.fetchall())
    result = []
    for row in rows:
        report = decode_report(row, with_body=False)
        try:
            authorize_report(user, report)
        except PermissionError:
            continue
        result.append(report)
    return result


def get_report(conn, user: dict, report_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM t_analysis_report WHERE id=%(id)s AND owner_id=%(owner)s", {"id": report_id, "owner": user["id"]})
        row = cur.fetchone()
    if not row:
        raise LookupError("报告不存在")
    report = decode_report(row)
    authorize_report(user, report)
    return report


def save_report(conn, user: dict, body: dict, required_permissions: list[str]) -> dict:
    owner = int(user["id"])
    series = digest({"owner": owner, "filters": body["filters"], "type": body["report_type"]})
    lock_name = "wb_report_" + series[:40]
    acquired = False
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT GET_LOCK(%(name)s, 5) AS acquired", {"name": lock_name})
            acquired = cur.fetchone()["acquired"] == 1
            if not acquired:
                raise ValueError("同口径报告正在保存，请稍后重试")
            # Current read after acquiring the lock, independent of an older transaction snapshot.
            cur.execute("SELECT version FROM t_analysis_report WHERE series_key=%(key)s ORDER BY version DESC LIMIT 1 FOR UPDATE", {"key": series})
            previous = cur.fetchone()
            version = previous["version"] + 1 if previous else 1
            report_id = str(uuid.uuid4())
            body = {**body, "version": version, "id": report_id}
            cur.execute("""INSERT INTO t_analysis_report
              (id,owner_id,series_key,version,title,report_type,filters_json,access_json,permissions_json,
               body_json,data_version,rules_version)
              VALUES (%(id)s,%(owner)s,%(series)s,%(version)s,%(title)s,%(type)s,%(filters)s,%(access)s,
                      %(permissions)s,%(body)s,%(data_version)s,%(rules_version)s)""",
                        {"id": report_id, "owner": owner, "series": series, "version": version,
                         "title": body["title"], "type": body["report_type"], "filters": canonical_json(body["filters"]),
                         "access": canonical_json(capture_scope(user, body["filters"])),
                         "permissions": canonical_json(required_permissions), "body": canonical_json(body),
                         "data_version": body["data_version"], "rules_version": body["rules_version"]})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if acquired:
                cur.execute("SELECT RELEASE_LOCK(%(name)s)", {"name": lock_name})
    return get_report(conn, user, report_id)
