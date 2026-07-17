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
    db_read_timeout: int = env_int("DB_READ_TIMEOUT", 600)
    db_write_timeout: int = env_int("DB_WRITE_TIMEOUT", 600)
    analytics_api_token: str = os.getenv("ANALYTICS_API_TOKEN", "")
    analytics_api_username: str = os.getenv("ANALYTICS_API_USERNAME", "analyst")
    analytics_rate_limit_per_minute: int = env_int("ANALYTICS_RATE_LIMIT_PER_MINUTE", 30)
    ark_analytics_enabled: bool = env_bool("ARK_ANALYTICS_ENABLED", False)
    ark_coding_chat_enabled: bool = env_bool("ARK_CODING_CHAT_ENABLED", False)
    ark_base_url: str = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3").rstrip("/")
    ark_api_key: str = os.getenv("ARK_API_KEY", "")
    ark_model: str = os.getenv("ARK_MODEL", "")
    ark_timeout_seconds: int = env_int("ARK_TIMEOUT_SECONDS", 20)
    ark_coding_max_output_tokens: int = env_int("ARK_CODING_MAX_OUTPUT_TOKENS", 1600)
    ark_coding_rate_limit_per_minute: int = env_int("ARK_CODING_RATE_LIMIT_PER_MINUTE", 20)
    ark_coding_daily_limit_per_user: int = env_int("ARK_CODING_DAILY_LIMIT_PER_USER", 50)
    ark_coding_daily_alert_threshold: int = env_int("ARK_CODING_DAILY_ALERT_THRESHOLD", 40)
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
        if self.analytics_api_token and len(self.analytics_api_token) < 24:
            problems.append("ANALYTICS_API_TOKEN must be at least 24 characters when enabled")
        if self.ark_analytics_enabled:
            if not self.ark_api_key:
                problems.append("ARK_API_KEY is required when ARK_ANALYTICS_ENABLED=true")
            if not self.ark_model:
                problems.append("ARK_MODEL is required when ARK_ANALYTICS_ENABLED=true")
            if not self.ark_base_url.startswith("https://"):
                problems.append("ARK_BASE_URL must use HTTPS")
        if self.ark_coding_chat_enabled:
            if not self.ark_api_key:
                problems.append("ARK_API_KEY is required when ARK_CODING_CHAT_ENABLED=true")
            if not self.ark_model:
                problems.append("ARK_MODEL is required when ARK_CODING_CHAT_ENABLED=true")
            if not self.ark_base_url.startswith("https://"):
                problems.append("ARK_BASE_URL must use HTTPS")
            if self.ark_coding_daily_limit_per_user < 0:
                problems.append("ARK_CODING_DAILY_LIMIT_PER_USER cannot be negative")
            if self.ark_coding_daily_alert_threshold < 0:
                problems.append("ARK_CODING_DAILY_ALERT_THRESHOLD cannot be negative")

        if problems:
            joined = "; ".join(problems)
            raise RuntimeError(f"Invalid production configuration: {joined}")


settings = Settings()
