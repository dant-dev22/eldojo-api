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
    """Entrada simple para verificar que el servicio arrancó."""

    return {
        "message": f"{settings.app_name} operativo",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
