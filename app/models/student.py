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
    current_belt_level_id: Mapped[int | None] = mapped_column(
        ForeignKey("belt_levels.id", ondelete="RESTRICT"),
        nullable=True,
    )
    current_stripe_id: Mapped[int | None] = mapped_column(
        ForeignKey("belt_stripes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    guardian_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    rd_victorias: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    rd_empates: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    rd_derrotas: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
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

    organization = relationship("Organization", back_populates="students")
    branch = relationship("Branch", back_populates="students")
    user = relationship("User", back_populates="students")
    primary_class = relationship("MartialClass", back_populates="students")
    current_belt_level = relationship("BeltLevel", back_populates="student_current_belts")
    current_stripe = relationship("BeltStripe", back_populates="student_current_stripes")
    class_enrollments = relationship("ClassEnrollment", back_populates="student")
    attendance_records = relationship("Attendance", back_populates="student")
    payments = relationship("Payment", back_populates="student")
    belt_histories = relationship("StudentBeltHistory", back_populates="student", cascade="all, delete-orphan")
    trajectory_events = relationship(
        "TrajectoryEvent",
        back_populates="student",
        cascade="all, delete-orphan",
        primaryjoin="and_(TrajectoryEvent.student_id==Student.id, TrajectoryEvent.deleted_at.is_(None))",
    )
    fight_records = relationship(
        "StudentFightRecord",
        back_populates="student",
        cascade="all, delete-orphan",
        primaryjoin="and_(StudentFightRecord.student_id==Student.id, StudentFightRecord.deleted_at.is_(None))",
    )
