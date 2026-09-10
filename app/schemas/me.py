"""Schemas del perfil móvil del alumno."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PaymentStatus, StudentStatus, UserRole


class AvailableClassRead(BaseModel):
    """Clase disponible para que el alumno la seleccione como principal."""

    id: int
    name: str
    description: str | None
    instructor_name: str | None
    is_active: bool


class MyProfileRead(BaseModel):
    """Perfil del alumno autenticado para la app móvil."""

    user_id: int
    student_id: int
    email: str
    role: UserRole
    unique_code: str
    first_name: str
    last_name: str
    full_name: str
    birth_date: date
    photo_url: str | None
    current_class_id: int | None
    payment_status: PaymentStatus
    next_payment_date: date | None
    status: StudentStatus
    available_classes: list[AvailableClassRead]


class MyPasswordChangeRequest(BaseModel):
    """Payload para que el alumno cambie su propia contraseña."""

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "MyPasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("La contraseña nueva y su confirmación no coinciden")
        if self.current_password == self.new_password:
            raise ValueError("La contraseña nueva debe ser distinta a la actual")
        return self


class MyEmailChangeRequest(BaseModel):
    """Payload para que el alumno cambie su propio correo."""

    new_email: str = Field(min_length=5, max_length=255)

    @field_validator("new_email")
    @classmethod
    def normalize_new_email(cls, value: str) -> str:
        return value.strip().lower()
