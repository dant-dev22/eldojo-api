"""Endpoints CRUD para organizaciones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import (
    ensure_can_create_organization,
    ensure_can_delete_organization,
    ensure_can_manage_organization,
    ensure_can_read_organization,
    scope_organization_filter,
)
from app.db.session import get_db
from app.models.user import User
from app.models.organization import Organization
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)


router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_organization_or_404(db: Session, organization_id: int) -> Organization:
    """Obtiene una organización existente o corta con 404."""

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organización no encontrada",
        )
    return organization


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Organization:
    """Crea una nueva organización tenant."""

    ensure_can_create_organization(current_user)
    organization = Organization(**payload.model_dump())
    db.add(organization)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la organización por un conflicto de integridad",
        ) from exc

    db.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Organization]:
    """Lista organizaciones con filtro opcional por estado."""

    query = select(Organization).order_by(Organization.id)
    scoped_organization_id = scope_organization_filter(current_user, organization_id=None)

    if scoped_organization_id is not None:
        query = query.where(Organization.id == scoped_organization_id)
    if is_active is not None:
        query = query.where(Organization.is_active == is_active)

    return list(db.scalars(query).all())


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Organization:
    """Devuelve una organización por su id."""

    ensure_can_read_organization(current_user, organization_id)
    return get_organization_or_404(db, organization_id)


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Organization:
    """Actualiza de forma parcial una organización."""

    ensure_can_manage_organization(current_user, organization_id)
    organization = get_organization_or_404(db, organization_id)
    changes = payload.model_dump(exclude_unset=True)

    for field_name, value in changes.items():
        setattr(organization, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la organización por un conflicto de integridad",
        ) from exc

    db.refresh(organization)
    return organization


@router.delete("/{organization_id}", response_model=MessageResponse)
def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Realiza borrado lógico desactivando la organización."""

    ensure_can_delete_organization(current_user)
    organization = get_organization_or_404(db, organization_id)
    organization.is_active = False
    db.commit()
    return MessageResponse(message="Organización desactivada correctamente")
