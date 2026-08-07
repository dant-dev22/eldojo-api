"""Schemas de alumnos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.enums import PaymentStatus, StudentStatus
from app.schemas.authorized_person import AuthorizedPersonRead
from app.schemas.belt import BeltLevelSummary, BeltStripeSummary
from app.schemas.emergency_contact import EmergencyContactRead
from app.schemas.medical_record import MedicalRecordRead
from app.schemas.student_document import StudentDocumentRead


class StudentBase(BaseModel):
    """Campos compartidos de alumno."""

    organization_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)
    user_id: int | None = Field(default=None, gt=0)
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    birth_date: date
    birth_place: str = Field(min_length=2, max_length=150)
    height_cm: int | None = Field(default=None, gt=0)
    photo_url: HttpUrl | None = None
    enrollment_date: date
    primary_class_id: int | None = Field(default=None, gt=0)
    current_belt_level_id: int | None = Field(default=None, gt=0)
    current_stripe_id: int | None = Field(default=None, gt=0)
    monthly_fee: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    next_payment_date: date | None = None
    payment_status: PaymentStatus = PaymentStatus.UP_TO_DATE
    status: StudentStatus = StudentStatus.ACTIVE
    guardian_name: str | None = Field(default=None, max_length=150)
    guardian_phone: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    is_minor: bool = False
    notes: str | None = None
    rd_victorias: int = Field(default=0, ge=0)
    rd_empates: int = Field(default=0, ge=0)
    rd_derrotas: int = Field(default=0, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normaliza la moneda a ISO 4217 en mayúsculas."""

        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_payment_fields(self) -> "StudentBase":
        """Asegura consistencia entre mensualidad y moneda."""

        if self.monthly_fee is not None and len(self.currency) != 3:
            raise ValueError("currency debe tener 3 letras")
        return self


class StudentCreate(StudentBase):
    """Payload para crear un alumno."""


class StudentUpdate(BaseModel):
    """Payload parcial para actualizar un alumno."""

    organization_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    birth_date: date | None = None
    birth_place: str | None = Field(default=None, min_length=2, max_length=150)
    height_cm: int | None = Field(default=None, gt=0)
    photo_url: HttpUrl | None = None
    enrollment_date: date | None = None
    primary_class_id: int | None = Field(default=None, gt=0)
    current_belt_level_id: int | None = Field(default=None, gt=0)
    current_stripe_id: int | None = Field(default=None, gt=0)
    monthly_fee: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    next_payment_date: date | None = None
    payment_status: PaymentStatus | None = None
    status: StudentStatus | None = None
    guardian_name: str | None = Field(default=None, max_length=150)
    guardian_phone: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    is_minor: bool | None = None
    notes: str | None = None
    rd_victorias: int | None = Field(default=None, ge=0)
    rd_empates: int | None = Field(default=None, ge=0)
    rd_derrotas: int | None = Field(default=None, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """Normaliza la moneda si viene en el request."""

        if value is None:
            return value
        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip().lower()


class StudentRead(BaseModel):
    """Representación pública de un alumno."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    branch_id: int
    unique_code: str
    user_id: int | None
    first_name: str
    last_name: str
    birth_date: date
    birth_place: str
    height_cm: int | None
    photo_url: str | None
    enrollment_date: date
    primary_class_id: int | None
    current_belt_level_id: int | None
    current_stripe_id: int | None
    monthly_fee: Decimal | None
    currency: str
    next_payment_date: date | None
    payment_status: PaymentStatus
    status: StudentStatus
    guardian_name: str | None
    guardian_phone: str | None
    phone: str | None
    email: str | None
    is_minor: bool
    notes: str | None
    rd_victorias: int
    rd_empates: int
    rd_derrotas: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    current_belt_level: BeltLevelSummary | None = None
    current_stripe: BeltStripeSummary | None = None
    emergency_contacts: list[EmergencyContactRead] | None = None
    medical_record: MedicalRecordRead | None = None
    documents: list[StudentDocumentRead] | None = None
    authorized_persons: list[AuthorizedPersonRead] | None = None
    profile_completeness: "StudentProfileCompleteness | None" = None


class StudentProfileCompleteness(BaseModel):
    """Diagnóstico de campos faltantes (para mostrar en dashboard)."""

    is_complete: bool
    total_fields: int
    filled_fields: int
    missing_fields: list[str]
    has_phone: bool
    has_email: bool
    has_emergency_contacts: bool
    has_medical_record: bool
    has_liability_waiver: bool
    has_photo_consent: bool
    has_authorized_persons_if_minor: bool
