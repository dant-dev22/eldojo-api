"""Endpoints mínimos de salud para la API y la conexión a DB."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db


router = APIRouter(tags=["health"])


@router.get("/health", summary="Estado básico de la API")
def health() -> dict[str, str | bool]:
    """Verifica que el proceso FastAPI esté vivo."""

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "debug": settings.app_debug,
    }


@router.get("/health/db", summary="Estado de la conexión a MySQL")
def health_db(db: Session = Depends(get_db)) -> dict[str, str | int]:
    """Ejecuta una consulta mínima y cuenta organizaciones como prueba real."""

    db.execute(text("SELECT 1"))
    total_organizations = db.execute(
        text("SELECT COUNT(*) FROM organizations")
    ).scalar_one()

    return {
        "status": "ok",
        "database": "connected",
        "organizations": total_organizations,
    }
