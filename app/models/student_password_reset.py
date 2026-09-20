"""Modelo ORM para tokens de reseteo de contraseña del alumno.

Generado por un admin desde el botón "Generar link" en la columna
"Portal alumno" del listado. El alumno canjea el token en la ruta
pública `/auth/student-password-reset/confirm` para establecer su
contraseña personalizada (sustituye la autogenerada/placeholder).

Usa tokens determinísticos (HMAC) igual que `StudentInvitationToken`:
    - `token_nonce` de 4 bytes para reconstruir el raw_token.
    - Último token pendiente por alumno: si hay 2, el más antiguo se
      invalida marcando used_at cuando se crea uno nuevo.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BINARY, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentPasswordResetToken(Base):
    """Token de un solo uso para cambiar la contraseña del alumno."""

    __tablename__ = "student_password_reset_tokens"

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
