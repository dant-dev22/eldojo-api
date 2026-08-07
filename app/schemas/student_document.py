"""Schemas para Documentos de Alumno (waiver, consentimiento, etc.)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StudentDocumentBase(BaseModel):
    student_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    document_type: str = Field(max_length=30)
    title: str = Field(min_length=2, max_length=255)
    file_url: str = Field(max_length=500)
    file_name: str | None = Field(default=None, max_length=255)
    file_size_bytes: int | None = Field(default=None, ge=0)
    signed_at: date | None = None
    signed_by_full_name: str | None = Field(default=None, max_length=200)
    witness_name: str | None = Field(default=None, max_length=200)
    expires_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class StudentDocumentCreate(StudentDocumentBase):
    pass


class StudentDocumentUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    organization_id: int | None = Field(default=None, gt=0)
    document_type: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, min_length=2, max_length=255)
    file_url: str | None = Field(default=None, max_length=500)
    file_name: str | None = Field(default=None, max_length=255)
    file_size_bytes: int | None = Field(default=None, ge=0)
    signed_at: date | None = None
    signed_by_full_name: str | None = Field(default=None, max_length=200)
    witness_name: str | None = Field(default=None, max_length=200)
    expires_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class StudentDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    document_type: str
    title: str
    file_url: str
    file_name: str | None
    file_size_bytes: int | None
    signed_at: date | None
    signed_by_full_name: str | None
    witness_name: str | None
    expires_at: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
