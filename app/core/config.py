"""Carga y expone la configuración principal del backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def as_bool(value: str | None, default: bool = False) -> bool:
    """Convierte variables string típicas a booleano."""

    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def as_list(value: str | None, default: list[str] | None = None) -> list[str]:
    """Convierte una lista separada por comas a una lista limpia."""

    if value is None:
        return default or []

    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


@dataclass(frozen=True)
class Settings:
    """Configuración mínima para arrancar la API."""

    app_name: str = os.getenv("APP_NAME", "ElDojo Backend API")
    app_env: str = os.getenv("APP_ENV", "development")
    app_debug: bool = as_bool(os.getenv("APP_DEBUG"), default=True)
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://eldojo_app:N7_xK9mP2_vQ@127.0.0.1:3306/eldojo_db",
    )
    auth_secret_key: str = os.getenv("AUTH_SECRET_KEY", "change-this-in-production-eldojo")
    auth_algorithm: str = os.getenv("AUTH_ALGORITHM", "HS256")
    auth_issuer: str = os.getenv("AUTH_ISSUER", "eldojo-backend-api")
    auth_access_token_expire_minutes: int = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    auth_refresh_token_expire_days: int = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    academy_verification_token_expire_hours: int = int(
        os.getenv("ACADEMY_VERIFICATION_TOKEN_EXPIRE_HOURS", "24")
    )
    academy_pending_session_expire_hours: int = int(
        os.getenv("ACADEMY_PENDING_SESSION_EXPIRE_HOURS", "24")
    )
    academy_verification_url_base: str = os.getenv(
        "ACADEMY_VERIFICATION_URL_BASE",
        "http://localhost:8081/confirmar-cuenta",
    )
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "465"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME")
    smtp_password: str | None = os.getenv("SMTP_PASSWORD")
    smtp_from_email: str | None = os.getenv("SMTP_FROM_EMAIL")
    smtp_from_name: str = os.getenv("SMTP_FROM_NAME", "ElDojo")
    backend_cors_origins: list[str] = field(
        default_factory=lambda: as_list(
            os.getenv(
                "BACKEND_CORS_ORIGINS",
                "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006,http://127.0.0.1:19006,http://localhost:3000,http://127.0.0.1:3000",
            )
        )
    )
    public_web_origin: str = os.getenv("PUBLIC_WEB_ORIGIN", "http://localhost:8081")
    app_web_origin: str = os.getenv("APP_WEB_ORIGIN", "http://localhost:8082")
    session_cookie_domain: str | None = os.getenv("SESSION_COOKIE_DOMAIN")
    session_ticket_ttl_seconds: int = int(os.getenv("SESSION_TICKET_TTL_SECONDS", "30"))
    uploads_dir: Path = Path(os.getenv("UPLOADS_DIR", str(BASE_DIR / "uploads")))
    uploads_url_prefix: str = os.getenv("UPLOADS_URL_PREFIX", "/uploads")


settings = Settings()
