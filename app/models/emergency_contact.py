"""Contacto de emergencia vinculado a un alumno."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmergencyContact(Base):
    """Contacto de emergencia para notificaciones urgentes."""

    __tablename__ = "emergency_contacts"

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
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    secondary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
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

    student = relationship("Student", back_populates="emergency_contacts")
    organization = relationship("Organization")
