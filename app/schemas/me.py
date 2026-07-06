"""Schemas del perfil móvil del alumno."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

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
