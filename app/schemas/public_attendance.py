"""Schemas para el flujo público manual de asistencias."""

from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class PublicAttendanceClassSchedule(BaseModel):
    """Horario semanal visible para elegir la clase sugerida."""

    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    start_time: time
    end_time: time


class PublicAttendanceClassOption(BaseModel):
    """Clase visible en el selector público."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    instructor_name: str | None
    schedules: list[PublicAttendanceClassSchedule] = Field(default_factory=list)


class PublicAttendanceStudentPreview(BaseModel):
    """Alumno resuelto a partir del identificador público."""

    id: int
    unique_code: str
    first_name: str
    last_name: str
    student_name: str


class PublicAttendanceContext(BaseModel):
    """Información mínima para renderizar la vista pública."""

    organization_name: str
    organization_slug: str
    branch_name: str
    branch_slug: str
    branch_id: int
    branch_timezone: str
    image_url: str | None = None
    classes: list[PublicAttendanceClassOption]


class PublicAttendanceCreate(BaseModel):
    """Payload público para registrar una asistencia manual."""

    student_id: int = Field(gt=0)
    class_id: int | None = Field(default=None, gt=0)


class PublicAttendanceResult(BaseModel):
    """Respuesta de una asistencia registrada desde el portal público."""

    message: str
    attendance_id: int
    student_id: int
    student_name: str
    class_id: int | None
    class_name: str | None
    check_in_at: datetime
