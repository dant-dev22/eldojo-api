"""Endpoints de autenticación."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.config import settings
from app.core.mail import (
    MailDeliveryError,
    build_academy_confirmation_url,
    send_academy_confirmation_email,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_email_verification_token,
    hash_email_verification_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.academy_pending_session import AcademyPendingSession
from app.models.email_verification import EmailVerificationToken
from app.models.organization import Organization
from app.models.enums import UserRole
from app.models.student import Student
from app.models.user import AdminAssignment, User
from app.schemas.auth import (
    AcademyConfirmRequest,
    AcademyPendingSessionRequest,
    AcademyPendingSessionStatusResponse,
    AcademyRegisterRequest,
    AcademyRegisterPendingResponse,
    AcademyResendConfirmationRequest,
    LoginRequest,
    RefreshRequest,
    StudentRegisterRequest,
    TokenResponse,
    TutorialStateUpdateRequest,
)
from app.schemas.user import UserRead


router = APIRouter(prefix="/auth", tags=["auth"])
PENDING_SESSION_POLLING_INTERVAL_SECONDS = 3


def utc_now() -> datetime:
    """Devuelve la fecha UTC naive usada por la base actual."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Busca un usuario por email con sus asignaciones administrativas."""

    query = (
        select(User)
        .options(selectinload(User.admin_assignments))
        .where(User.email == email)
    )
    return db.scalar(query)


def build_token_response(user: User) -> TokenResponse:
    """Genera el par access/refresh token para una sesión autenticada."""

    access_token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    refresh_token, refresh_expires_in = create_refresh_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        refresh_expires_in=refresh_expires_in,
        user=UserRead.model_validate(user),
    )


def build_pending_confirmation_response(
    *,
    email: str,
    email_sent: bool,
    pending_session_ticket: str,
) -> AcademyRegisterPendingResponse:
    """Construye la respuesta estándar para cuentas pendientes de confirmación."""

    if email_sent:
        message = "Te enviamos un enlace de confirmación para activar tu cuenta."
    else:
        message = (
            "Tu registro quedó pendiente, pero no pudimos enviar el correo. "
            "Solicita un reenvío desde la pantalla de acceso."
        )

    return AcademyRegisterPendingResponse(
        email=email,
        email_sent=email_sent,
        message=message,
        verification_expires_in_hours=settings.academy_verification_token_expire_hours,
        pending_session_ticket=pending_session_ticket,
        pending_session_expires_in_hours=settings.academy_pending_session_expire_hours,
        polling_interval_seconds=PENDING_SESSION_POLLING_INTERVAL_SECONDS,
    )


def is_pending_confirmation_user(user: User) -> bool:
    """Indica si el usuario quedó pendiente de confirmar su correo."""

    return user.email_verified_at is None and not user.is_active


def invalidate_verification_tokens(db: Session, user_id: int, *, used_at: datetime | None = None) -> None:
    """Marca como usados todos los tokens pendientes del usuario."""

    timestamp = used_at or utc_now()
    pending_tokens = db.scalars(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == user_id)
        .where(EmailVerificationToken.used_at.is_(None))
    ).all()

    for token in pending_tokens:
        token.used_at = timestamp


def invalidate_pending_session_tickets(db: Session, user_id: int, *, used_at: datetime | None = None) -> None:
    """Marca como usados todos los tickets de autologin pendientes del usuario."""

    timestamp = used_at or utc_now()
    pending_tickets = db.scalars(
        select(AcademyPendingSession)
        .where(AcademyPendingSession.user_id == user_id)
        .where(AcademyPendingSession.used_at.is_(None))
    ).all()

    for ticket in pending_tickets:
        ticket.used_at = timestamp


def activate_pending_session_tickets(db: Session, user_id: int, *, activated_at: datetime | None = None) -> None:
    """Habilita los tickets vigentes del usuario una vez confirmado el correo."""

    timestamp = activated_at or utc_now()
    pending_tickets = db.scalars(
        select(AcademyPendingSession)
        .where(AcademyPendingSession.user_id == user_id)
        .where(AcademyPendingSession.used_at.is_(None))
        .where(AcademyPendingSession.activated_at.is_(None))
    ).all()

    for ticket in pending_tickets:
        if ticket.expires_at > timestamp:
            ticket.activated_at = timestamp


def issue_verification_token(db: Session, user: User) -> str:
    """Genera y persiste un nuevo token de confirmación para el usuario."""

    invalidate_verification_tokens(db, user.id)
    raw_token = generate_email_verification_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_email_verification_token(raw_token),
            expires_at=utc_now() + timedelta(hours=settings.academy_verification_token_expire_hours),
        )
    )
    return raw_token


def issue_pending_session_ticket(db: Session, user: User) -> str:
    """Genera y persiste un ticket temporal para autologin web post confirmación."""

    invalidate_pending_session_tickets(db, user.id)
    raw_ticket = generate_email_verification_token()
    db.add(
        AcademyPendingSession(
            user_id=user.id,
            ticket_hash=hash_email_verification_token(raw_ticket),
            expires_at=utc_now() + timedelta(hours=settings.academy_pending_session_expire_hours),
        )
    )
    return raw_ticket


def get_pending_session_by_ticket(db: Session, raw_ticket: str) -> AcademyPendingSession | None:
    """Busca un ticket temporal a partir de su valor sin exponer el hash en cliente."""

    return db.scalar(
        select(AcademyPendingSession).where(
            AcademyPendingSession.ticket_hash == hash_email_verification_token(raw_ticket)
        )
    )


def deliver_confirmation_email(user: User, raw_token: str) -> bool:
    """Intenta enviar el correo de confirmación sin exponer errores SMTP al cliente."""

    recipient_name = " ".join(
        part for part in [user.first_name or "", user.last_name or ""] if part
    ).strip() or "equipo"

    try:
        send_academy_confirmation_email(
            recipient_email=user.email,
            recipient_name=recipient_name,
            confirmation_url=build_academy_confirmation_url(raw_token),
        )
    except MailDeliveryError:
        return False

    return True


def normalize_academy_name(value: str) -> str:
    """Normaliza un nombre de academia para comparaciones y slugs."""

    return " ".join(value.strip().split())


def academy_letters(value: str) -> str:
    """Conserva solo letras ASCII para construir slugs estables de 3 caracteres."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z]", "", ascii_value).upper()


def build_slug_candidates(academy_name: str) -> list[str]:
    """Genera candidatos de slug coherentes tomando letras del nombre sin espacios."""

    letters = academy_letters(academy_name)
    if len(letters) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre de la academia debe contener al menos 3 letras",
        )

    candidates: list[str] = []
    seen: set[str] = set()

    def append_candidate(candidate: str) -> None:
        if len(candidate) != 3 or candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    append_candidate(letters[:3])

    for start in range(1, len(letters) - 2):
        append_candidate(letters[start : start + 3])

    append_candidate(f"{letters[0]}{letters[1]}{letters[-1]}")
    append_candidate(f"{letters[0]}{letters[-2]}{letters[-1]}")

    return candidates


def organization_exists_by_name(db: Session, academy_name: str) -> bool:
    """Detecta si ya existe una academia con el mismo nombre normalizado."""

    normalized_name = normalize_academy_name(academy_name).lower()
    existing_id = db.scalar(
        select(Organization.id).where(func.lower(Organization.name) == normalized_name)
    )
    return existing_id is not None


def resolve_available_organization_slug(db: Session, academy_name: str) -> str:
    """Selecciona el primer slug libre derivado del nombre de la academia."""

    for candidate in build_slug_candidates(academy_name):
        slug_in_use = db.scalar(select(Organization.id).where(Organization.slug == candidate))
        if slug_in_use is None:
            return candidate

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No fue posible generar un código corto disponible para la academia",
    )


def build_duplicate_error(exc: IntegrityError, default_detail: str) -> HTTPException:
    """Mapea conflictos de integridad a mensajes entendibles para autenticación."""

    raw_error = str(exc.orig).lower()

    if "users.email" in raw_error or "for key 'email'" in raw_error or "user.email" in raw_error:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese usuario ya existe",
        )

    if (
        "organizations.slug" in raw_error
        or "for key 'slug'" in raw_error
        or "organization.slug" in raw_error
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esa academia ya existe",
        )

    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=default_detail)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Autentica credenciales y devuelve un Bearer token."""

    user = get_user_by_email(db, payload.email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No existe una cuenta con ese correo",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña no es correcta",
        )

    if not user.is_active:
        if user.email_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu cuenta aun no ha sido confirmada. Revisa tu correo o solicita un nuevo enlace.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario está inactivo",
        )

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post(
    "/academy/register",
    response_model=AcademyRegisterPendingResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_academy(
    payload: AcademyRegisterRequest,
    db: Session = Depends(get_db),
) -> AcademyRegisterPendingResponse:
    """Crea una academia pendiente y envía un enlace de confirmación al admin inicial."""

    normalized_academy_name = normalize_academy_name(payload.academy_name)
    if organization_exists_by_name(db, normalized_academy_name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa academia ya existe")

    existing_user = get_user_by_email(db, payload.email)
    if existing_user is not None:
        detail = "Ese usuario ya existe"
        if is_pending_confirmation_user(existing_user):
            detail = "Ya existe un registro pendiente con ese correo. Revisa tu correo o solicita un reenvío."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    organization = Organization(
        name=normalized_academy_name,
        slug=resolve_available_organization_slug(db, normalized_academy_name),
        is_active=False,
    )
    user = User(
        first_name=payload.admin_first_name,
        last_name=payload.admin_last_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ORG_ADMIN,
        is_active=False,
        email_verified_at=None,
        first_time=True,
        last_login_at=None,
    )

    db.add(organization)
    raw_token = ""
    raw_pending_session_ticket = ""

    try:
        db.flush()
        user.admin_assignments.append(
            AdminAssignment(
                organization_id=organization.id,
                branch_id=None,
            )
        )
        db.add(user)
        db.flush()
        raw_token = issue_verification_token(db, user)
        raw_pending_session_ticket = issue_pending_session_ticket(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise build_duplicate_error(exc, "No fue posible crear la academia") from exc

    return build_pending_confirmation_response(
        email=payload.email,
        email_sent=deliver_confirmation_email(user, raw_token),
        pending_session_ticket=raw_pending_session_ticket,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Renueva la sesión usando un refresh token válido."""

    try:
        token_payload = decode_refresh_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        ) from exc

    user = db.get(User, int(token_payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario autenticado no encontrado")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario está inactivo",
        )

    return build_token_response(user)


@router.post("/student/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_student(payload: StudentRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Vincula un alumno existente con credenciales propias para la app."""

    student = db.scalar(
        select(Student)
        .where(Student.unique_code == payload.unique_code)
        .where(Student.deleted_at.is_(None))
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de alumno no encontrado")
    if student.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este alumno ya tiene una cuenta vinculada",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.STUDENT,
        is_active=True,
        first_time=True,
    )
    db.add(user)

    try:
        db.flush()
        student.user_id = user.id
        user.email_verified_at = utc_now()
        user.last_login_at = utc_now()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise build_duplicate_error(exc, "No fue posible registrar al alumno con esos datos") from exc

    db.refresh(user)
    return build_token_response(user)


@router.post("/academy/confirm", response_model=TokenResponse)
def confirm_academy_registration(
    payload: AcademyConfirmRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Activa una cuenta de academia usando un token de confirmación válido."""

    verification_token = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_email_verification_token(payload.token)
        )
    )
    if verification_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El enlace de confirmación es inválido",
        )

    if verification_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Este enlace de confirmación ya fue utilizado",
        )

    now = utc_now()
    if verification_token.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="El enlace de confirmación ha expirado",
        )

    user = db.get(User, verification_token.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cuenta asociada ya no existe",
        )

    user.is_active = True
    user.email_verified_at = now
    user.last_login_at = now
    verification_token.used_at = now
    invalidate_verification_tokens(db, user.id, used_at=now)
    activate_pending_session_tickets(db, user.id, activated_at=now)

    organizations = db.scalars(
        select(Organization)
        .join(AdminAssignment, AdminAssignment.organization_id == Organization.id)
        .where(AdminAssignment.user_id == user.id)
    ).all()
    for organization in organizations:
        organization.is_active = True

    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post("/academy/resend-confirmation", response_model=AcademyRegisterPendingResponse)
def resend_academy_confirmation(
    payload: AcademyResendConfirmationRequest,
    db: Session = Depends(get_db),
) -> AcademyRegisterPendingResponse:
    """Reenvía el correo de confirmación para una cuenta pendiente."""

    user = get_user_by_email(db, payload.email)
    if user is None or user.role != UserRole.ORG_ADMIN or not is_pending_confirmation_user(user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe una cuenta pendiente con ese correo",
        )

    raw_token = issue_verification_token(db, user)
    db.commit()

    return build_pending_confirmation_response(
        email=user.email,
        email_sent=deliver_confirmation_email(user, raw_token),
        pending_session_ticket="",
    )


@router.post("/academy/pending-session/status", response_model=AcademyPendingSessionStatusResponse)
def get_academy_pending_session_status(
    payload: AcademyPendingSessionRequest,
    db: Session = Depends(get_db),
) -> AcademyPendingSessionStatusResponse:
    """Expone el estado del ticket temporal que espera la confirmación por correo."""

    pending_session = get_pending_session_by_ticket(db, payload.ticket)
    if pending_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La espera de confirmación ya no es válida para este navegador.",
        )

    now = utc_now()
    if pending_session.used_at is not None:
        return AcademyPendingSessionStatusResponse(
            status="used",
            message="La sesión pendiente ya fue consumida.",
        )
    if pending_session.expires_at <= now:
        return AcademyPendingSessionStatusResponse(
            status="expired",
            message="La espera de confirmación expiró. Vuelve a iniciar el registro o entra manualmente.",
        )
    if pending_session.activated_at is None:
        return AcademyPendingSessionStatusResponse(
            status="pending_confirmation",
            message="Seguimos esperando la confirmación del correo.",
        )

    return AcademyPendingSessionStatusResponse(
        status="ready",
        message="La cuenta ya fue confirmada. Puedes iniciar sesión automáticamente.",
    )


@router.post("/academy/pending-session/redeem", response_model=TokenResponse)
def redeem_academy_pending_session(
    payload: AcademyPendingSessionRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Canjea un ticket temporal listo para abrir la sesión en el navegador web."""

    pending_session = get_pending_session_by_ticket(db, payload.ticket)
    if pending_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La espera de confirmación ya no es válida para este navegador.",
        )

    now = utc_now()
    if pending_session.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="La sesión pendiente ya fue consumida.",
        )
    if pending_session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="La espera de confirmación expiró. Vuelve a iniciar el registro o entra manualmente.",
        )
    if pending_session.activated_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta todavía no ha sido confirmada desde el correo.",
        )

    user = db.get(User, pending_session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La cuenta asociada ya no existe.",
        )
    if not user.is_active or user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta todavía no está lista para iniciar sesión.",
        )

    user.last_login_at = now
    pending_session.used_at = now
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(require_active_user)) -> User:
    """Devuelve el usuario autenticado por el Bearer token."""

    return current_user


@router.patch("/me/tutorial-state", response_model=UserRead)
def update_tutorial_state(
    payload: TutorialStateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> User:
    """Actualiza la bandera del tutorial inicial del usuario autenticado."""

    current_user.first_time = payload.first_time
    db.commit()
    db.refresh(current_user)
    return current_user
