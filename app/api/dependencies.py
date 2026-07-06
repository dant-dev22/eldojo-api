"""Dependencias compartidas de la capa API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import TokenDecodeError, decode_access_token
from app.db.session import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Obtiene el usuario autenticado a partir del Bearer token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un Bearer token válido",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        ) from exc

    user_id = int(payload["sub"])
    query = (
        select(User)
        .options(selectinload(User.admin_assignments))
        .where(User.id == user_id)
    )
    user = db.scalar(query)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario autenticado no encontrado")
    return user


def require_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Asegura que el usuario autenticado siga activo."""

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario autenticado está inactivo",
        )
    return current_user
