"""Schemas Pydantic para el sistema de trayectoria / recuerdos de alumnos."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrajectoryEventBase(BaseModel):
    """Campos compartidos de un suceso de trayectoria."""

    event_date: date
    content: str = Field(min_length=1, max_length=280)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("El contenido no puede estar vacío")
        if len(stripped) > 280:
            raise ValueError("El contenido no puede exceder 280 caracteres")
        return stripped


class TrajectoryEventCreate(TrajectoryEventBase):
    """Payload para registrar un nuevo suceso en la trayectoria de un alumno."""

    student_id: int = Field(gt=0)


class TrajectoryEventUpdate(BaseModel):
    """Payload parcial para actualizar un suceso de trayectoria."""

    event_date: date | None = None
    content: str | None = Field(default=None, min_length=1, max_length=280)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("El contenido no puede estar vacío")
        if len(stripped) > 280:
            raise ValueError("El contenido no puede exceder 280 caracteres")
        return stripped


class TrajectoryEventRead(BaseModel):
    """Representación pública de un suceso de trayectoria."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    event_date: date
    content: str
    created_by_user_id: int | None
    created_at: datetime
    updated_at: datetime


class StudentTrajectorySummary(BaseModel):
    """Resumen de trayectoria para listados: conteo de sucesos y última fecha."""

    model_config = ConfigDict(from_attributes=True)

    student_id: int
    total_events: int
    first_event_date: date | None
    last_event_date: date | None
