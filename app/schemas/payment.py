"""Schemas de pagos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import PaymentMethod, PaymentRecordStatus


class PaymentBase(BaseModel):
    """Campos compartidos entre creación y edición de pagos."""

    student_id: int = Field(gt=0)
    organization_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    period_start: date
    period_end: date
    paid_at: datetime
    method: PaymentMethod
    status: PaymentRecordStatus
    recorded_by: int = Field(gt=0)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normaliza la moneda a ISO 4217 en mayúsculas."""

        return value.strip().upper()

    @model_validator(mode="after")
    def validate_period_range(self) -> "PaymentBase":
        """Verifica que el rango del período sea cronológicamente válido."""

        if self.period_start > self.period_end:
            raise ValueError("period_start no puede ser mayor que period_end")
        return self


class PaymentCreate(PaymentBase):
    """Payload para crear un pago."""


class PaymentUpdate(BaseModel):
    """Payload parcial para actualizar un pago."""

    student_id: int | None = Field(default=None, gt=0)
    organization_id: int | None = Field(default=None, gt=0)
    branch_id: int | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    period_start: date | None = None
    period_end: date | None = None
    paid_at: datetime | None = None
    method: PaymentMethod | None = None
    status: PaymentRecordStatus | None = None
    recorded_by: int | None = Field(default=None, gt=0)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """Normaliza la moneda si viene en el request."""

        if value is None:
            return value
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_period_range(self) -> "PaymentUpdate":
        """Valida el rango del período solo si ambas fechas llegan en el request."""

        if self.period_start is not None and self.period_end is not None and self.period_start > self.period_end:
            raise ValueError("period_start no puede ser mayor que period_end")
        return self


class PaymentRead(BaseModel):
    """Representación pública de un pago."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    organization_id: int
    branch_id: int
    amount: Decimal
    currency: str
    period_start: date
    period_end: date
    paid_at: datetime
    method: PaymentMethod
    status: PaymentRecordStatus
    recorded_by: int
    notes: str | None
    created_at: datetime
