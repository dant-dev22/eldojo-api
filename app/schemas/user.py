"""Schemas de usuarios y sus alcances administrativos."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


class AdminScopeRead(BaseModel):
    """Representa el alcance administrativo principal expuesto por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    branch_id: int | None
    created_at: datetime


class UserCreate(BaseModel):
    """Payload para crear un usuario autenticable."""

    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    is_active: bool = True
    organization_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        """Normaliza espacios en nombres visibles."""

        if value is None:
            return value
        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normaliza el email para evitar duplicados por mayúsculas."""

        return value.strip().lower()


class UserUpdate(BaseModel):
    """Payload parcial para editar un usuario."""

    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None
    organization_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        """Normaliza espacios en nombres visibles cuando llegan en el request."""

        if value is None:
            return value
        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        """Normaliza el email solo si llega en el request."""

        if value is None:
            return value
        return value.strip().lower()


class UserRead(BaseModel):
    """Representación pública de un usuario sin exponer el hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str | None
    last_name: str | None
    email: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    admin_assignments: list[AdminScopeRead]
