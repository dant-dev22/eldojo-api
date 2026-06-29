"""Base declarativa compartida por los modelos ORM del backend."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base para los modelos SQLAlchemy del backend."""

    pass
