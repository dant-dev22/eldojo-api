"""Modelo ORM para tickets temporales de autologin tras confirmar una academia."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AcademyPendingSession(Base):
    """Ticket temporal que habilita el login web cuando el correo ya fue confirmado."""

    __tablename__ = "academy_pending_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="academy_pending_sessions")
