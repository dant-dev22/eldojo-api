"""Schemas de horarios de clase."""

from __future__ import annotations

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClassScheduleBase(BaseModel):
    """Campos compartidos entre creación y edición de horarios."""

    class_id: int = Field(gt=0)
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "ClassScheduleBase":
        """Asegura que la hora de inicio sea menor a la hora final."""

        if self.start_time >= self.end_time:
            raise ValueError("start_time debe ser menor que end_time")
        return self


class ClassScheduleCreate(ClassScheduleBase):
    """Payload para crear un horario de clase."""


class ClassScheduleUpdate(BaseModel):
    """Payload parcial para editar un horario de clase."""

    class_id: int | None = Field(default=None, gt=0)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "ClassScheduleUpdate":
        """Valida el rango de horas solo si ambos valores llegan."""

        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("start_time debe ser menor que end_time")
        return self


class ClassScheduleRead(BaseModel):
    """Representación pública de un horario semanal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    day_of_week: int
    start_time: time
    end_time: time
    created_at: datetime
