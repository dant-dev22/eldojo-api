"""Modelo ORM para tickets de sincronización de sesión entre subdominios."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionSyncTicket(Base):
    """Ticket de un solo uso para transferir la sesión desde el sitio público al dashboard.

    Vida típica: 30 segundos. Consumido por GET en app.eldojo.tech/?session_ticket=xxx
    y redimido contra /auth/session-ticket/redeem.
    """

    __tablename__ = "session_sync_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User")
