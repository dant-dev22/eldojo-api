"""Schemas de organizaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationBase(BaseModel):
    """Campos compartidos entre creación y edición de organizaciones."""

    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(min_length=3, max_length=3)
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Fuerza el slug a 3 letras mayúsculas."""

        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("slug debe contener exactamente 3 letras")
        return normalized


class OrganizationCreate(OrganizationBase):
    """Payload para crear una organización."""


class OrganizationUpdate(BaseModel):
    """Payload parcial para editar una organización."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    slug: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        """Normaliza el slug solo si llega en el request."""

        if value is None:
            return value
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("slug debe contener exactamente 3 letras")
        return normalized


class OrganizationRead(BaseModel):
    """Representación pública de una organización."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
