from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pymysql
from pymysql.cursors import DictCursor

from app.config import settings


@dataclass(frozen=True)
class DbUrl:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str


def parse_database_url(url: str | None = None) -> DbUrl:
    parsed = urlparse(url or settings.database_url)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise ValueError("DATABASE_URL must use mysql+pymysql://")
    query = parse_qs(parsed.query)
    return DbUrl(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 3306,
        user=unquote(parsed.username or "root"),
        password=unquote(parsed.password or ""),
        database=(parsed.path or "/order_manager").lstrip("/"),
        charset=query.get("charset", ["utf8mb4"])[0],
    )


@contextmanager
def connection(database: str | None = None):
    cfg = parse_database_url()
    conn = pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=database if database is not None else cfg.database,
        charset=cfg.charset,
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchone()


def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            return list(cur.fetchall())
