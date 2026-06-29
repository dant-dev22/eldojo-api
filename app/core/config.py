"""Carga y expone la configuración principal del backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def as_bool(value: str | None, default: bool = False) -> bool:
    """Convierte variables string típicas a booleano."""

    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


settings = Settings()
