"""Punto de entrada de la API FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Entrada simple para verificar que el servicio arrancó."""

    return {
        "message": f"{settings.app_name} operativo",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
