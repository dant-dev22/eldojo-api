"""Endpoints de autenticación."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.organization import Organization
from app.models.enums import UserRole
from app.models.student import Student
from app.models.user import AdminAssignment, User
from app.schemas.auth import (
    AcademyRegisterRequest,
    LoginRequest,
    RefreshRequest,
    StudentRegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario está inactivo",
        )

    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@router.post("/academy/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_academy(payload: AcademyRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Crea una academia con su administrador inicial y devuelve sesión autenticada."""

    normalized_academy_name = normalize_academy_name(payload.academy_name)
    if organization_exists_by_name(db, normalized_academy_name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esa academia ya existe")

    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese usuario ya existe")

    organization = Organization(
        name=normalized_academy_name,
        slug=resolve_available_organization_slug(db, normalized_academy_name),
        is_active=True,
    )
    user = User(
        first_name=payload.admin_first_name,
        last_name=payload.admin_last_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ORG_ADMIN,
        is_active=True,
        last_login_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    db.add(organization)

    try:
        db.flush()
        user.admin_assignments.append(
            AdminAssignment(
                organization_id=organization.id,
                branch_id=None,
            )
        )
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise build_duplicate_error(exc, "No fue posible crear la academia") from exc

    created_user = get_user_by_email(db, payload.email)
    if created_user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La academia se creó pero no fue posible recuperar la sesión inicial",
        )

    return build_token_response(created_user)


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
    )
    db.add(user)

    try:
        db.flush()
        student.user_id = user.id
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise build_duplicate_error(exc, "No fue posible registrar al alumno con esos datos") from exc

    db.refresh(user)
    return build_token_response(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(require_active_user)) -> User:
    """Devuelve el usuario autenticado por el Bearer token."""

    return current_user
