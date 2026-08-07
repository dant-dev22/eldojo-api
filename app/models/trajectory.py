"""Modelos ORM para el sistema de trayectoria / recuerdos de alumnos."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrajectoryEvent(Base):
    """Suceso / recuerdo registrado en la trayectoria de un alumno.

    Cada evento pertenece a un día específico (event_date) y tiene un texto
    descriptivo corto (máx 280 caracteres, similar a un tweet), por ejemplo:
    "Graduación cinta azul", "Primer torneo oficial", etc.
    """

    __tablename__ = "trajectory_events"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(content) <= 280",
            name="chk_trajectory_events_content_length",
        ),
        CheckConstraint(
            "event_date IS NOT NULL",
            name="chk_trajectory_events_event_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(280), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    student = relationship("Student", back_populates="trajectory_events")
    organization = relationship("Organization")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
