"""Modelo ORM mínimo de alumnos para operar el CRUD inicial."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentStatus, StudentStatus, db_enum


class Student(Base):
    """Alumno inscrito en una sucursal."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unique_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date(), nullable=False)
    birth_place: Mapped[str] = mapped_column(String(150), nullable=False)
    height_cm: Mapped[int | None] = mapped_column(nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    enrollment_date: Mapped[date] = mapped_column(Date(), nullable=False)
    primary_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    monthly_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'USD'"))
    next_payment_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        db_enum(PaymentStatus, name="student_payment_status"),
        nullable=False,
    )
    status: Mapped[StudentStatus] = mapped_column(
        db_enum(StudentStatus, name="student_status"),
        nullable=False,
    )
    guardian_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    organization = relationship("Organization", back_populates="students")
    branch = relationship("Branch", back_populates="students")
    user = relationship("User", back_populates="students")
    primary_class = relationship("MartialClass", back_populates="students")
    class_enrollments = relationship("ClassEnrollment", back_populates="student")
    attendance_records = relationship("Attendance", back_populates="student")
