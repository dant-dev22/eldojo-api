"""Schemas para Personas Autorizadas (retiro de menores)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthorizedPersonBase(BaseModel):
    student_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=200)
    relationship: str | None = Field(default=None, max_length=80)
    dni_type: str | None = Field(default=None, max_length=20)
    dni_number: str = Field(min_length=2, max_length=80)
    dni_verified: bool = False
    dni_verified_by_user_id: int | None = Field(default=None, gt=0)
    dni_photo_url: str | None = Field(default=None, max_length=500)
    phone: str = Field(min_length=3, max_length=50)
    secondary_phone: str | None = Field(default=None, max_length=50)
    photo_url: str | None = Field(default=None, max_length=500)
    authorization_notes: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class AuthorizedPersonCreate(AuthorizedPersonBase):
    pass


class AuthorizedPersonUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    organization_id: int | None = Field(default=None, gt=0)
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    relationship: str | None = Field(default=None, max_length=80)
    dni_type: str | None = Field(default=None, max_length=20)
    dni_number: str | None = Field(default=None, min_length=2, max_length=80)
    dni_verified: bool | None = None
    dni_verified_by_user_id: int | None = Field(default=None, gt=0)
    dni_photo_url: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, min_length=3, max_length=50)
    secondary_phone: str | None = Field(default=None, max_length=50)
    photo_url: str | None = Field(default=None, max_length=500)
    authorization_notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class AuthorizedPersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    full_name: str
    relationship: str | None
    dni_type: str | None
    dni_number: str
    dni_verified: bool
    dni_verified_by_user_id: int | None
    dni_photo_url: str | None
    phone: str
    secondary_phone: str | None
    photo_url: str | None
    authorization_notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
