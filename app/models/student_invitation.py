"""Modelo ORM para tokens de invitación de activación del portal del alumno."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BINARY, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentInvitationToken(Base):
    """Token de un solo uso para activar el portal del alumno.

    Generado por un admin cuando habilita `enable_portal_access` durante
    la creación o edición de un alumno. El alumno canjea el token en la
    ruta pública `/auth/student-invitation/redeem` para establecer sus
    credenciales, verificar su correo y acceder a su perfil por primera vez.

    Desde 2026-09-10 usa tokens determinísticos (HMAC). El campo
    `token_nonce` almacena el nonce de 4 bytes necesario para
    reconstruir el raw_token cuando el admin quiera volver a copiar
    el enlace sin regenerarlo.
    """

    __tablename__ = "student_invitation_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    token_plain_tail: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )
    token_nonce: Mapped[bytes | None] = mapped_column(
        BINARY(4),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(),
        nullable=True,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_sent_to: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    student = relationship("Student")
    user = relationship("User", foreign_keys=[user_id])
    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])
