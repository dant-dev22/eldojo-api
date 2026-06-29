"""Schemas de sucursales."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BranchBase(BaseModel):
    """Campos compartidos entre creación y edición de sucursales."""

    name: str = Field(min_length=2, max_length=150)
    country: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=255)
    timezone: str = Field(min_length=3, max_length=64)
    qr_secret: str = Field(min_length=8, max_length=255)
    is_active: bool = True

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Asegura que la zona horaria sea una IANA válida."""

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone debe ser una zona IANA válida") from exc
        return value


class BranchCreate(BranchBase):
    """Payload para crear una sucursal."""

    organization_id: int = Field(gt=0)


class BranchUpdate(BaseModel):
    """Payload parcial para editar una sucursal."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    address: str | None = Field(default=None, min_length=5, max_length=255)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    qr_secret: str | None = Field(default=None, min_length=8, max_length=255)
    is_active: bool | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        """Valida la zona horaria solo si llega en el request."""

        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone debe ser una zona IANA válida") from exc
        return value


class BranchRead(BaseModel):
    """Representación pública de una sucursal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    country: str
    state: str
    city: str
    address: str
    timezone: str
    qr_secret: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
