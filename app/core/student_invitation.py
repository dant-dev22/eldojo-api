"""Helpers para tokens de invitación del portal del alumno.

Centraliza la generación, hasheo, validación y búsqueda de tokens
de invitación para evitar duplicar lógica entre rutas admin y auth.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_email_verification_token
from app.models.student_invitation import StudentInvitationToken


def _utc_now_naive() -> datetime:
    """Devuelve el momento actual en UTC naive (coherente con la BD)."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def student_invitation_expires_at() -> datetime | None:
    """Calcula la fecha de expiración de una nueva invitación.

    Si `STUDENT_INVITATION_TOKEN_EXPIRE_DAYS` no está definido (None) o
    es <= 0, devuelve None, lo que significa que la invitación NUNCA
    expira (hasta que es utilizada o invalidada manualmente).
    """

    days = settings.student_invitation_token_expire_days
    if days is None or days <= 0:
        return None
    return _utc_now_naive() + timedelta(days=days)


def generate_student_invitation_token() -> tuple[str, str, str]:
    """Genera un token nuevo y devuelve (raw, hash_sha256, ultimos_8_chars).

    - raw_token: el valor que se envía al cliente y NUNCA se guarda en BD.
    - token_hash: SHA-256 hex del raw (64 chars), único en la tabla.
    - token_plain_tail: últimos 8 chars del raw, para auditoría sin leak.
    """

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_email_verification_token(raw_token)
    token_plain_tail = raw_token[-8:] if len(raw_token) >= 8 else raw_token
    return raw_token, token_hash, token_plain_tail


def build_student_invitation_link(raw_token: str) -> str:
    """Construye la URL pública que el admin comparte con el alumno."""

    base = settings.student_invitation_url_base.rstrip("/")
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode({'token': raw_token})}"


def invalidate_student_invitations(
    db: Session,
    *,
    student_id: int | None = None,
    user_id: int | None = None,
    used_at: datetime | None = None,
) -> int:
    """Marca como usados TODOS los tokens pendientes de un alumno/usuario.

    Devuelve la cantidad de tokens invalidados.
    """

    if student_id is None and user_id is None:
        raise ValueError("Se requiere student_id o user_id para invalidar invitaciones")

    predicates = [StudentInvitationToken.used_at.is_(None)]
    if student_id is not None:
        predicates.append(StudentInvitationToken.student_id == student_id)
    if user_id is not None:
        predicates.append(StudentInvitationToken.user_id == user_id)

    timestamp = used_at or _utc_now_naive()
    pending = db.scalars(
        select(StudentInvitationToken).where(and_(*predicates))
    ).all()

    for token in pending:
        token.used_at = timestamp
    return len(pending)


def find_pending_student_invitation_by_raw(
    db: Session,
    raw_token: str,
) -> StudentInvitationToken | None:
    """Busca un token válido (no usado, no expirado) a partir del valor raw.

    Devuelve el ORM StudentInvitationToken (con relaciones student y user
    precargadas) o None si no existe, ya fue usado o expiró.
    """

    if not raw_token:
        return None

    token_hash = hash_email_verification_token(raw_token)
    stmt = (
        select(StudentInvitationToken)
        .where(StudentInvitationToken.token_hash == token_hash)
    )
    invitation = db.scalar(stmt)
    if invitation is None:
        return None
    if invitation.used_at is not None:
        return None
    if invitation.expires_at is not None and invitation.expires_at <= _utc_now_naive():
        return None
    return invitation
