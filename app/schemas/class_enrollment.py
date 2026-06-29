"""Schemas de inscripciones de alumnos a clases."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClassEnrollmentBase(BaseModel):
    """Campos compartidos entre creación y edición de inscripciones."""

    student_id: int = Field(gt=0)
    class_id: int = Field(gt=0)
    enrolled_at: datetime
    is_active: bool = True


class ClassEnrollmentCreate(ClassEnrollmentBase):
    """Payload para crear una inscripción."""


class ClassEnrollmentUpdate(BaseModel):
    """Payload parcial para actualizar una inscripción."""

    student_id: int | None = Field(default=None, gt=0)
    class_id: int | None = Field(default=None, gt=0)
    enrolled_at: datetime | None = None
    is_active: bool | None = None


class ClassEnrollmentRead(BaseModel):
    """Representación pública de una inscripción."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    class_id: int
    enrolled_at: datetime
    is_active: bool
    created_at: datetime
