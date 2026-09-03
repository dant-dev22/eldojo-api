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


class MartialClassReadSummary(BaseModel):
    """Resumen de clase asociado a una asistencia."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    discipline_name: str | None = None
    instructor_name: str | None = None


class StudentReadSummary(BaseModel):
    """Resumen de alumno asociado a una asistencia."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    unique_code: str
    first_name: str
    last_name: str


class AttendanceRead(BaseModel):
    """Representación pública de una asistencia.

    Incluye relaciones anidadas resumidas para evitar N+1 queries
    en vistas que muestran el historial de asistencias por alumno
    o por clase.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    class_id: int | None
    branch_id: int
    check_in_at: datetime
    method: AttendanceMethod
    registered_by: int | None
    created_at: datetime

    class_obj: MartialClassReadSummary | None = None
    student: StudentReadSummary | None = None


class AttendanceSummaryPerClass(BaseModel):
    """Conteo de asistencias por clase individual."""

    class_id: int
    class_name: str
    count: int


class StudentAttendanceSummary(BaseModel):
    """KPIs y agregados de asistencias para un alumno específico."""

    student_id: int
    total_attendances: int
    last_7_days: int
    last_30_days: int
    by_class: list[AttendanceSummaryPerClass]
    first_attendance_at: datetime | None
    last_attendance_at: datetime | None
    streak_days: int
