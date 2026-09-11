"""Helpers para tokens de invitación del portal del alumno.

Centraliza la generación, hasheo, validación y búsqueda de tokens
de invitación para evitar duplicar lógica entre rutas admin y auth.

Versión 2026-09-10: Tokens determinísticos (HMAC) para garantizar que
sólo exista UN link válido por alumno hasta su canje o expiración (48h).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_email_verification_token
from app.models.student_invitation import StudentInvitationToken

STUDENT_INVITATION_TTL_HOURS: int = 48
STUDENT_INVITATION_HMAC_NAMESPACE: bytes = b"eldojo:student_invitation:v1"
STUDENT_INVITATION_NONCE_BYTES: int = 4


def _utc_now_naive() -> datetime:
    """Devuelve el momento actual en UTC naive (coherente con la BD)."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def _student_invitation_hmac_key() -> bytes:
    """Deriva una clave HMAC a partir del AUTH_SECRET_KEY.

    Usa un namespace fijo para evitar colisión con otras firmas (JWT,
    session tickets, etc.) incluso aunque compartan la misma raíz.
    """

    base = settings.auth_secret_key.encode("utf-8")
    return hashlib.sha256(STUDENT_INVITATION_HMAC_NAMESPACE + base).digest()


def _b64url_encode(raw_bytes: bytes) -> str:
    """Codifica bytes en Base64 URL-safe sin padding."""

    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    """Decodifica Base64 URL-safe restaurando el padding faltante."""

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def student_invitation_expires_at() -> datetime:
    """Calcula la fecha de expiración de una nueva invitación.

    Desde 2026-09-10 el TTL es FIJO a 48 horas. La variable de entorno
    `STUDENT_INVITATION_TOKEN_EXPIRE_DAYS` se ignora y emite un
    DeprecationWarning si está configurada.
    """

    if settings.student_invitation_token_expire_days is not None:
        warnings.warn(
            "STUDENT_INVITATION_TOKEN_EXPIRE_DAYS está deprecated y será "
            "ignorada. El TTL de invitaciones es ahora fijo de 48 horas.",
            DeprecationWarning,
            stacklevel=2,
        )
    return _utc_now_naive() + timedelta(hours=STUDENT_INVITATION_TTL_HOURS)


def generate_deterministic_student_invitation_token(
    *,
    student_id: int,
    nonce: bytes,
    created_at: datetime,
) -> tuple[str, str, str]:
    """Genera un token DETERMINÍSTICO a partir de (student_id, nonce, created_at).

    El resultado es idempotente: con los mismos parámetros de entrada se
    obtiene exactamente el mismo raw_token. Esto permite reconstruir el
    link público (sin almacenarlo) en cualquier momento posterior a la
    creación, siempre que el token siga pendiente.

    Estructura del raw_token (ambos segmentos en b64url sin padding):
        {hmac_28bytes}.{nonce_4bytes}

    Returns
    -------
    raw_token: str
        El valor que se envía al cliente.
    token_hash: str
        SHA-256 hex (64 chars) del raw_token, índice único en la tabla.
    token_plain_tail: str
        Últimos 8 chars del raw_token (auditoría).
    """

    if len(nonce) != STUDENT_INVITATION_NONCE_BYTES:
        raise ValueError(
            f"nonce debe tener {STUDENT_INVITATION_NONCE_BYTES} bytes, "
            f"recibido {len(nonce)}"
        )

    # Truncar created_at a granularidad de segundos para evitar drift por
    # microsegundos al leer de vuelta desde MySQL.
    created_seconds = int(created_at.timestamp())
    signing_input = (
        f"student={student_id};"
        f"nonce={nonce.hex()};"
        f"created={created_seconds}"
    )
    key = _student_invitation_hmac_key()
    digest = hmac.new(key, signing_input.encode("ascii"), hashlib.sha256).digest()

    hmac_segment = _b64url_encode(digest[:28])
    nonce_segment = _b64url_encode(nonce)
    raw_token = f"{hmac_segment}.{nonce_segment}"

    token_hash = hash_email_verification_token(raw_token)
    token_plain_tail = raw_token[-8:] if len(raw_token) >= 8 else raw_token
    return raw_token, token_hash, token_plain_tail


def generate_student_invitation_token() -> tuple[str, str, str, bytes]:
    """Wrapper legacy + nuevo: genera un token con nonce aleatorio nuevo.

    Mantiene compatibilidad con las firmas existentes para el caller,
    pero además devuelve el nonce generado para persistirlo en la BD.

    Retorna (raw_token, token_hash, token_plain_tail, nonce_bytes).
    """

    raise RuntimeError(
        "generate_student_invitation_token() fue reemplazada por "
        "generate_deterministic_student_invitation_token(). Por favor usa "
        "la firma determinística para garantizar unicidad del link."
    )


def generate_student_invitation_nonce() -> bytes:
    """Devuelve un nonce criptográficamente aleatorio de 4 bytes."""

    return secrets.token_bytes(STUDENT_INVITATION_NONCE_BYTES)


def reconstruct_student_invitation_token(
    token_row: StudentInvitationToken,
) -> str | None:
    """Reconstruye el raw_token a partir de una fila ORM existente.

    Para ello necesitamos que la fila tenga `token_nonce` populado
    (campo introducido en 2026-09-10). Las filas legacy (nonce=None)
    NO son reconstruibles: devuelve None y el caller debería forzar
    la generación de una invitación nueva.

    Nota de seguridad: esta función sólo debe usarse en endpoints de
    admin (requieren scope admin). El endpoint público `/auth/student-
    invitation` sigue validando por SHA-256 contra `token_hash`.
    """

    if token_row.token_nonce is None or token_row.created_at is None:
        return None
    if not isinstance(token_row.token_nonce, (bytes, bytearray)):
        return None
    try:
        raw_token, _, _ = generate_deterministic_student_invitation_token(
            student_id=int(token_row.student_id),
            nonce=bytes(token_row.token_nonce),
            created_at=token_row.created_at,
        )
    except Exception:
        return None
    return raw_token


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
