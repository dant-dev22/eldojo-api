"""Persona autorizada para retirar a un alumno menor de edad."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship as sa_relationship

from app.db.base import Base


class AuthorizedPerson(Base):
    """Persona autorizada para retirar al alumno del Dojo (menores)."""

    __tablename__ = "authorized_persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dni_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dni_number: Mapped[str] = mapped_column(String(80), nullable=False)
    dni_verified: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("0"),
    )
    dni_verified_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    dni_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    secondary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authorization_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("1"),
    )
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

    student = sa_relationship("Student", back_populates="authorized_persons")
    organization = sa_relationship("Organization")
    verified_by_user = sa_relationship("User")
