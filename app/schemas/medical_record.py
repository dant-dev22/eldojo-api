"""Schemas para Ficha Médica."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


BLOOD_TYPES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}


class MedicalRecordBase(BaseModel):
    student_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    blood_type: str | None = Field(default=None, max_length=10)
    allergies: str | None = None
    previous_injuries: str | None = None
    insurance_type: str = Field(default="none", max_length=20)
    insurance_provider: str | None = Field(default=None, max_length=200)
    insurance_policy_number: str | None = Field(default=None, max_length=150)
    chronic_conditions: str | None = None
    medications: str | None = None
    physician_name: str | None = Field(default=None, max_length=200)
    physician_phone: str | None = Field(default=None, max_length=50)
    tetanus_vaccine_date: date | None = None
    additional_notes: str | None = None

    @classmethod
    def validate_blood_type(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().upper().replace(" ", "")
        if cleaned not in BLOOD_TYPES:
            raise ValueError(f"Tipo de sangre inválido. Opciones: {sorted(BLOOD_TYPES)}")
        return cleaned


class MedicalRecordCreate(MedicalRecordBase):
    pass


class MedicalRecordUpdate(BaseModel):
    student_id: int | None = Field(default=None, gt=0)
    organization_id: int | None = Field(default=None, gt=0)
    blood_type: str | None = Field(default=None, max_length=10)
    allergies: str | None = None
    previous_injuries: str | None = None
    insurance_type: str | None = Field(default=None, max_length=20)
    insurance_provider: str | None = Field(default=None, max_length=200)
    insurance_policy_number: str | None = Field(default=None, max_length=150)
    chronic_conditions: str | None = None
    medications: str | None = None
    physician_name: str | None = Field(default=None, max_length=200)
    physician_phone: str | None = Field(default=None, max_length=50)
    tetanus_vaccine_date: date | None = None
    additional_notes: str | None = None


class MedicalRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    blood_type: str | None
    allergies: str | None
    previous_injuries: str | None
    insurance_type: str
    insurance_provider: str | None
    insurance_policy_number: str | None
    chronic_conditions: str | None
    medications: str | None
    physician_name: str | None
    physician_phone: str | None
    tetanus_vaccine_date: date | None
    additional_notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
