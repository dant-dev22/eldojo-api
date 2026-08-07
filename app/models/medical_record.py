"""Ficha médica por alumno (relación 1:1)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InsuranceType(str):
    PUBLIC = "public"
    PRIVATE = "private"
    NONE = "none"


class MedicalRecord(Base):
    """Registro médico confidencial de un alumno."""

    __tablename__ = "medical_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    blood_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text(), nullable=True)
    previous_injuries: Mapped[str | None] = mapped_column(Text(), nullable=True)
    insurance_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'none'"),
    )
    insurance_provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text(), nullable=True)
    medications: Mapped[str | None] = mapped_column(Text(), nullable=True)
    physician_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    physician_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tetanus_vaccine_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    additional_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    student = relationship("Student", back_populates="medical_record")
    organization = relationship("Organization")
