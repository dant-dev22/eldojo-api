"""Schemas de disciplinas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DisciplineBase(BaseModel):
    """Campos compartidos para disciplinas por organizacion."""

    name: str = Field(min_length=2, max_length=100)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Normaliza el nombre para evitar variantes inconsistentes."""

        return value.strip().upper()


class DisciplineCreate(DisciplineBase):
    """Payload para crear una disciplina."""

    organization_id: int = Field(gt=0)


class DisciplineRead(BaseModel):
    """Representacion publica de una disciplina."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    is_active: bool
    created_at: datetime
