"""Endpoints CRUD para sucursales."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import (
    ensure_can_create_branch,
    ensure_can_manage_branch,
    scope_branch_filter,
)
from app.db.session import get_db
from app.models.organization import Branch, Organization
from app.models.user import User
from app.schemas.branch import BranchCreate, BranchRead, BranchUpdate
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/branches", tags=["branches"])


def get_branch_or_404(db: Session, branch_id: int) -> Branch:
    """Obtiene una sucursal existente o corta con 404."""

    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")
    return branch


def ensure_organization_exists(db: Session, organization_id: int) -> None:
    """Verifica que la organización exista antes de crear la sucursal."""

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organización no encontrada")


@router.post("", response_model=BranchRead, status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Branch:
    """Crea una sucursal ligada a una organización existente."""

    ensure_can_create_branch(current_user, payload.organization_id)
    ensure_organization_exists(db, payload.organization_id)
    branch = Branch(**payload.model_dump())
    db.add(branch)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la sucursal por un conflicto de integridad",
        ) from exc

    db.refresh(branch)
    return branch


@router.get("", response_model=list[BranchRead])
def list_branches(
    organization_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Branch]:
    """Lista sucursales con filtros básicos."""

    organization_id, branch_id = scope_branch_filter(
        current_user,
        organization_id=organization_id,
        branch_id=None,
    )
    query = select(Branch).order_by(Branch.id)

    if organization_id is not None:
        query = query.where(Branch.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(Branch.id == branch_id)
    if is_active is not None:
        query = query.where(Branch.is_active == is_active)

    return list(db.scalars(query).all())


@router.get("/{branch_id}", response_model=BranchRead)
def get_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Branch:
    """Devuelve una sucursal por su id."""

    branch = get_branch_or_404(db, branch_id)
    ensure_can_manage_branch(current_user, branch.organization_id, branch.id)
    return branch


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: int,
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Branch:
    """Actualiza de forma parcial una sucursal."""

    branch = get_branch_or_404(db, branch_id)
    ensure_can_manage_branch(current_user, branch.organization_id, branch.id)
    changes = payload.model_dump(exclude_unset=True)

    for field_name, value in changes.items():
        setattr(branch, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la sucursal por un conflicto de integridad",
        ) from exc

    db.refresh(branch)
    return branch


@router.delete("/{branch_id}", response_model=MessageResponse)
def delete_branch(
    branch_id: int,
    force: bool = Query(default=False, description="Si es true, intenta borrado físico."),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina una sucursal de forma lógica o física según el modo elegido."""

    branch = get_branch_or_404(db, branch_id)
    ensure_can_create_branch(current_user, branch.organization_id)

    if not force:
        branch.is_active = False
        db.commit()
        return MessageResponse(message="Sucursal desactivada correctamente")

    db.delete(branch)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede borrar físicamente la sucursal porque tiene historial relacionado",
        ) from exc

    return MessageResponse(message="Sucursal eliminada físicamente")
