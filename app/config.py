from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:your_password@127.0.0.1:3306/order_manager?charset=utf8mb4",
    )
    secret_key: str = os.getenv("APP_SECRET_KEY", "dev-order-manager-secret")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    importer_password: str = os.getenv("IMPORTER_PASSWORD", "importer123")
    analyst_password: str = os.getenv("ANALYST_PASSWORD", "analyst123")
    viewer_password: str = os.getenv("VIEWER_PASSWORD", "viewer123")


settings = Settings()
