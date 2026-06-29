"""Modelos mínimos de clases y horarios para operar CRUD básico."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AttendanceMethod, db_enum


class MartialClass(Base):
    """Clase disponible en una sucursal."""

    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    discipline_id: Mapped[int] = mapped_column(
        ForeignKey("disciplines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    instructor_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    capacity: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
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

    organization = relationship("Organization", back_populates="classes")
    branch = relationship("Branch", back_populates="classes")
    discipline = relationship("Discipline", back_populates="classes")
    students = relationship("Student", back_populates="primary_class")
    schedules = relationship("ClassSchedule", back_populates="class_obj")
    enrollments = relationship("ClassEnrollment", back_populates="class_obj")
    attendance_records = relationship("Attendance", back_populates="class_obj")


class ClassSchedule(Base):
    """Horario semanal recurrente de una clase."""

    __tablename__ = "class_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    class_obj = relationship("MartialClass", back_populates="schedules")


class ClassEnrollment(Base):
    """Inscripción activa o histórica de un alumno a una clase."""

    __tablename__ = "class_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    student = relationship("Student", back_populates="class_enrollments")
    class_obj = relationship("MartialClass", back_populates="enrollments")


class Attendance(Base):
    """Registro de check-in del alumno."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    class_id: Mapped[int | None] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    check_in_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    method: Mapped[AttendanceMethod] = mapped_column(
        db_enum(AttendanceMethod, name="attendance_method"),
        nullable=False,
    )
    registered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("UTC_TIMESTAMP()"),
    )

    student = relationship("Student", back_populates="attendance_records")
    class_obj = relationship("MartialClass", back_populates="attendance_records")
    branch = relationship("Branch", back_populates="attendance_records")
    registered_by_user = relationship("User", back_populates="attendance_records")
