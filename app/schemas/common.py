"""Schemas compartidos por varios endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Respuesta simple para operaciones que no devuelven un recurso."""

    message: str
