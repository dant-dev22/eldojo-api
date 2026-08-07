"""Schemas para cinturones, stripes e historial de promociones."""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _validate_hex_color(value: str, *, field_name: str) -> str:
    if not _HEX_COLOR.match(value):
        raise ValueError(f"{field_name} debe ser un color HEX válido (#RRGGBB)")
    return value.upper()


class BeltLevelBase(BaseModel):
    """Campos compartidos de un nivel de cinta."""

    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=150)
    color_hex: str = Field(min_length=7, max_length=7)
    text_color_hex: str = Field(default="#FFFFFF", min_length=7, max_length=7)
    order_index: int = Field(default=0, ge=0)
    is_active: bool = True
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("color_hex")
    @classmethod
    def normalize_color_hex(cls, value: str) -> str:
        return _validate_hex_color(value, field_name="color_hex")

    @field_validator("text_color_hex")
    @classmethod
    def normalize_text_color_hex(cls, value: str) -> str:
        return _validate_hex_color(value, field_name="text_color_hex")


class BeltLevelCreate(BeltLevelBase):
    """Payload para crear un nivel de cinta."""


class BeltLevelUpdate(BaseModel):
    """Payload parcial para actualizar un nivel de cinta."""

    organization_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    color_hex: str | None = Field(default=None, min_length=7, max_length=7)
    text_color_hex: str | None = Field(default=None, min_length=7, max_length=7)
    order_index: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("color_hex")
    @classmethod
    def normalize_color_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_hex_color(value, field_name="color_hex")

    @field_validator("text_color_hex")
    @classmethod
    def normalize_text_color_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_hex_color(value, field_name="text_color_hex")


class BeltStripeBase(BaseModel):
    """Campos compartidos de un stripe/punto."""

    belt_level_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=150)
    color_hex: str = Field(min_length=7, max_length=7)
    order_index: int = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("color_hex")
    @classmethod
    def normalize_color_hex(cls, value: str) -> str:
        return _validate_hex_color(value, field_name="color_hex")


class BeltStripeCreate(BeltStripeBase):
    """Payload para crear un stripe."""


class BeltStripeUpdate(BaseModel):
    """Payload parcial para actualizar un stripe."""

    belt_level_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    color_hex: str | None = Field(default=None, min_length=7, max_length=7)
    order_index: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("color_hex")
    @classmethod
    def normalize_color_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_hex_color(value, field_name="color_hex")


class BeltStripeRead(BaseModel):
    """Representación pública de un stripe."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    belt_level_id: int
    name: str
    display_name: str
    color_hex: str
    order_index: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BeltLevelRead(BaseModel):
    """Representación pública de un nivel de cinta (con stripes anidados)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    display_name: str
    color_hex: str
    text_color_hex: str
    order_index: int
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime
    stripes: list[BeltStripeRead] = Field(default_factory=list)


class BeltLevelSummary(BaseModel):
    """Representación mínima de un nivel de cinta para listas."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    color_hex: str
    text_color_hex: str
    order_index: int
    is_active: bool


class BeltStripeSummary(BaseModel):
    """Representación mínima de un stripe para listas."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    belt_level_id: int
    name: str
    display_name: str
    color_hex: str
    order_index: int
    is_active: bool


class StudentBeltHistoryCreate(BaseModel):
    """Payload para registrar un cambio de cinta."""

    student_id: int = Field(gt=0)
    belt_level_id: int = Field(gt=0)
    stripe_id: int | None = Field(default=None, gt=0)
    awarded_at: date
    awarded_by_user_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)
    update_student_current: bool = Field(
        default=True,
        description="Si es True, actualiza los campos current_belt_level_id y current_stripe_id del alumno.",
    )


class StudentBeltHistoryRead(BaseModel):
    """Representación pública del historial de promociones."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    belt_level_id: int
    stripe_id: int | None
    awarded_at: date
    awarded_by_user_id: int | None
    notes: str | None
    created_at: datetime
    belt_level: BeltLevelSummary | None = None
    stripe: BeltStripeSummary | None = None
