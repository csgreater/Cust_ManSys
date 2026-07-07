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


def env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development").lower()
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:your_password@127.0.0.1:3306/order_manager?charset=utf8mb4",
    )
    secret_key: str = os.getenv("APP_SECRET_KEY", "dev-order-manager-secret")
    secure_cookies: bool = env_bool("APP_SECURE_COOKIES", False)
    session_max_age: int = env_int("APP_SESSION_MAX_AGE", 60 * 60 * 8)
    session_same_site: str = os.getenv("APP_SESSION_SAME_SITE", "lax")
    max_upload_mb: int = env_int("APP_MAX_UPLOAD_MB", 50)
    db_connect_timeout: int = env_int("DB_CONNECT_TIMEOUT", 10)
    db_read_timeout: int = env_int("DB_READ_TIMEOUT", 60)
    db_write_timeout: int = env_int("DB_WRITE_TIMEOUT", 60)
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    importer_password: str = os.getenv("IMPORTER_PASSWORD", "importer123")
    analyst_password: str = os.getenv("ANALYST_PASSWORD", "analyst123")
    viewer_password: str = os.getenv("VIEWER_PASSWORD", "viewer123")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate_for_runtime(self) -> None:
        if not self.is_production:
            return

        problems: list[str] = []
        if self.secret_key in {"dev-order-manager-secret", "change-this-secret-key"} or len(self.secret_key) < 32:
            problems.append("APP_SECRET_KEY must be a strong random value with at least 32 characters")
        if "://root:" in self.database_url or "://root@" in self.database_url:
            problems.append("DATABASE_URL should use a dedicated application database user, not root")
        if "your_password" in self.database_url:
            problems.append("DATABASE_URL still contains the placeholder password")
        default_passwords = {
            "ADMIN_PASSWORD": (self.admin_password, "admin123"),
            "IMPORTER_PASSWORD": (self.importer_password, "importer123"),
            "ANALYST_PASSWORD": (self.analyst_password, "analyst123"),
            "VIEWER_PASSWORD": (self.viewer_password, "viewer123"),
        }
        for key, (actual, default) in default_passwords.items():
            if actual == default:
                problems.append(f"{key} must be changed before production startup")
        if self.secure_cookies is not True:
            problems.append("APP_SECURE_COOKIES=true is required when APP_ENV=production")

        if problems:
            joined = "; ".join(problems)
            raise RuntimeError(f"Invalid production configuration: {joined}")


settings = Settings()
