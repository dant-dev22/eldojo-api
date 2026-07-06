"""Schemas de clases."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClassBase(BaseModel):
    """Campos compartidos entre creación y edición de clases."""

    organization_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)
    discipline_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    instructor_name: str | None = Field(default=None, max_length=150)
    capacity: int | None = Field(default=None, gt=0)
    is_active: bool = True


class ClassCreate(ClassBase):
    """Payload para crear una clase."""


class ClassUpdate(BaseModel):
    """Payload parcial para editar una clase."""

    organization_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    discipline_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    instructor_name: str | None = Field(default=None, max_length=150)
    capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ClassRead(BaseModel):
    """Representación pública de una clase."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    branch_id: int
    discipline_id: int
    discipline_name: str | None = None
    name: str
    description: str | None
    instructor_name: str | None
    capacity: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
