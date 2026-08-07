"""Schemas para Contacto de Emergencia."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmergencyContactBase(BaseModel):
    student_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=200)
    relationship: str | None = Field(default=None, max_length=80)
    phone: str = Field(min_length=3, max_length=50)
    secondary_phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    priority: int = Field(default=1, ge=1)
    notes: str | None = Field(default=None, max_length=300)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        try:
            EmailStr._validate(value)
        except Exception:
            raise ValueError("Email inválido")
        return value.strip().lower()

    @field_validator("phone", "secondary_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = "".join(ch for ch in value if ch.isdigit() or ch == "+")
        return digits if digits else value


class EmergencyContactCreate(EmergencyContactBase):
    pass


class EmergencyContactUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    organization_id: int | None = Field(default=None, gt=0)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    relationship: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, min_length=3, max_length=50)
    secondary_phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    priority: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=300)


class EmergencyContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    full_name: str
    relationship: str | None
    phone: str
    secondary_phone: str | None
    email: str | None
    priority: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
