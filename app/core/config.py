"""Carga y expone la configuración principal del backend."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=True)



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
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
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
    student_invitation_token_expire_days: int = int(
        os.getenv("STUDENT_INVITATION_TOKEN_EXPIRE_DAYS", "7")
    )
    student_invitation_url_base: str = os.getenv(
        "STUDENT_INVITATION_URL_BASE",
        "http://localhost:8081/activar",
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
                "https://eldojo.tech,https://www.eldojo.tech,https://app.eldojo.tech,http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082,http://127.0.0.1:8082,http://localhost:19006,http://127.0.0.1:19006,http://localhost:3000,http://127.0.0.1:3000",
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


def _validate_runtime_secrets() -> None:
    """Validación de seguridad ejecutada en import-time.

    Evita que un deploy de producción arrance con AUTH_SECRET_KEY por
    defecto, lo que causaría la invalidación de TODAS las sesiones JWT
    activas en cada restart / deploy (por rotación implícita del secret).
    """

    is_production_like = (
        settings.app_env == "production"
        or settings.app_debug is False
    )

    if not is_production_like:
        return

    DEFAULT_AUTH_SECRET = "change-this-in-production-eldojo"

    if not settings.auth_secret_key or settings.auth_secret_key == DEFAULT_AUTH_SECRET:
        raise RuntimeError(
            "[FATAL] AUTH_SECRET_KEY está usando el valor por defecto o está vacía "
            f"en un entorno de producción (APP_ENV={settings.app_env!r}, "
            f"APP_DEBUG={settings.app_debug}). ESTO INVALIDA TODAS LAS SESIONES "
            "CADA VEZ QUE EL BACKEND REINICIA. Configura AUTH_SECRET_KEY como "
            "un string aleatorio permanente en tu .env de producción antes de arrancar."
        )

    if (
        not settings.auth_issuer
        or len(settings.auth_issuer) < 4
        or settings.auth_issuer.isspace()
    ):
        raise RuntimeError(
            "[FATAL] AUTH_ISSUER no está configurada correctamente en producción. "
            "Sin un issuer fijo, los tokens JWT no se validan de forma estable."
        )


_validate_runtime_secrets()
