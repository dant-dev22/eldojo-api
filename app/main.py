"""Punto de entrada de la API FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Content-Length", "Authorization", "X-Request-ID"],
    max_age=3600,
)

settings.uploads_dir.mkdir(parents=True, exist_ok=True)
app.state.uploads_dir = settings.uploads_dir
app.state.uploads_url_prefix = settings.uploads_url_prefix
app.mount(
    settings.uploads_url_prefix,
    StaticFiles(directory=settings.uploads_dir),
    name="uploads",
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Entrada simple para verificar que el servicio arranco."""

    return {
        "message": f"{settings.app_name} operativo",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
        "version": f"{settings.api_v1_prefix}/version",
    }


@app.get("/version", tags=["root"])
@app.get("/api/v1/version", tags=["health"])
def version() -> dict[str, str]:
    """Version del backend y informacion de deploy.

    El frontend usa este endpoint (y tambien version.json estatico) para
    detectar si hay una nueva version desplegada y forzar reload.
    """

    return {
        "version": settings.app_version,
        "backend_version": settings.app_version,
        "environment": settings.app_env,
    }
