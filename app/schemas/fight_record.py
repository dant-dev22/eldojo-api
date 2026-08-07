"""Schemas Pydantic para registros de peleas / encuentros deportivos."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.fight_record import FightRecordType


class StudentFightRecordBase(BaseModel):
    """Campos compartidos de un registro de pelea."""

    record_type: FightRecordType
    opponent_name: str = Field(min_length=1, max_length=50)
    fight_date: date

    @field_validator("opponent_name")
    @classmethod
    def trim_opponent(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("El nombre del rival no puede estar vacío")
        if len(stripped) > 50:
            raise ValueError("El nombre del rival no puede exceder 50 caracteres")
        return stripped


class StudentFightRecordCreate(StudentFightRecordBase):
    """Payload para registrar un nuevo encuentro deportivo."""

    student_id: int = Field(gt=0)


class StudentFightRecordUpdate(BaseModel):
    """Payload parcial para actualizar un registro de pelea."""

    record_type: FightRecordType | None = None
    opponent_name: str | None = Field(default=None, min_length=1, max_length=50)
    fight_date: date | None = None

    @field_validator("opponent_name")
    @classmethod
    def trim_opponent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("El nombre del rival no puede estar vacío")
        if len(stripped) > 50:
            raise ValueError("El nombre del rival no puede exceder 50 caracteres")
        return stripped


class StudentFightRecordRead(BaseModel):
    """Representación pública de un registro de pelea."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    student_id: int
    record_type: FightRecordType
    opponent_name: str
    fight_date: date
    created_at: datetime
    updated_at: datetime
