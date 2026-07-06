"""Endpoints de autenticación."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
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
from app.models.enums import UserRole
from app.models.student import Student
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, StudentRegisterRequest, TokenResponse
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible registrar al alumno con esos datos",
        ) from exc

    db.refresh(user)
    return build_token_response(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(require_active_user)) -> User:
    """Devuelve el usuario autenticado por el Bearer token."""

    return current_user
