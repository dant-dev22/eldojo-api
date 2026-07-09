"""Schemas para el flujo público de asistencias."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicAttendanceClassOption(BaseModel):
    """Clase visible en el selector público."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    instructor_name: str | None


class PublicAttendanceContext(BaseModel):
    """Información mínima para renderizar la vista pública."""

    organization_name: str
    organization_slug: str
    branch_name: str
    branch_slug: str
    branch_id: int
    image_url: str | None = None
    classes: list[PublicAttendanceClassOption]


class PublicAttendanceCreate(BaseModel):
    """Payload público para registrar una asistencia mediante QR."""

    student_code: str = Field(min_length=1, max_length=32)
    class_id: int | None = Field(default=None, gt=0)
    qr_token: str = Field(min_length=1, max_length=1024)


class PublicAttendanceResult(BaseModel):
    """Respuesta de una asistencia registrada desde el portal público."""

    message: str
    attendance_id: int
    student_id: int
    student_name: str
    class_id: int | None
    class_name: str | None
    check_in_at: datetime
