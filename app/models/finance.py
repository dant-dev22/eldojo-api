"""Modelo ORM mínimo de pagos para operar el CRUD inicial."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentMethod, PaymentRecordStatus, db_enum


class Payment(Base):
    """Pago registrado a un alumno."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        db_enum(PaymentMethod, name="payment_method"),
        nullable=False,
    )
    status: Mapped[PaymentRecordStatus] = mapped_column(
        db_enum(PaymentRecordStatus, name="payment_record_status"),
        nullable=False,
    )
    recorded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    student = relationship("Student", back_populates="payments")
    organization = relationship("Organization", back_populates="payments")
    branch = relationship("Branch", back_populates="payments")
    recorded_by_user = relationship("User", back_populates="payments_recorded")
