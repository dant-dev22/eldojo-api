"""Schemas de asistencia."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttendanceMethod


class AttendanceBase(BaseModel):
    """Campos compartidos entre creación y edición de asistencia."""

    student_id: int = Field(gt=0)
    class_id: int | None = Field(default=None, gt=0)
    branch_id: int = Field(gt=0)
    check_in_at: datetime
    method: AttendanceMethod
    registered_by: int | None = Field(default=None, gt=0)


class AttendanceCreate(AttendanceBase):
    """Payload para crear un registro de asistencia."""


class AttendanceUpdate(BaseModel):
    """Payload parcial para editar un registro de asistencia."""

    student_id: int | None = Field(default=None, gt=0)
    class_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    check_in_at: datetime | None = None
    method: AttendanceMethod | None = None
    registered_by: int | None = Field(default=None, gt=0)


class AttendanceRead(BaseModel):
    """Representación pública de una asistencia."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    class_id: int | None
    branch_id: int
    check_in_at: datetime
    method: AttendanceMethod
    registered_by: int | None
    created_at: datetime
