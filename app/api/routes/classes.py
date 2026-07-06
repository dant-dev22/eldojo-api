"""Endpoints CRUD para clases."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
from app.db.session import get_db
from app.models.curriculum import Discipline
from app.models.organization import Branch, Organization
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.class_ import ClassCreate, ClassRead, ClassUpdate
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/classes", tags=["classes"])


def get_class_or_404(db: Session, class_id: int) -> MartialClass:
    """Obtiene una clase existente o corta con 404."""

    class_obj = db.get(MartialClass, class_id)
    if class_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
    return class_obj


def validate_class_links(
    db: Session,
    *,
    organization_id: int,
    branch_id: int,
    discipline_id: int,
) -> None:
    """Valida coherencia entre organización, sucursal y disciplina."""

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organización no encontrada")

    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")
    if branch.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La sucursal no pertenece a la organización indicada",
        )

    discipline = db.get(Discipline, discipline_id)
    if discipline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disciplina no encontrada")
    if discipline.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La disciplina no pertenece a la organización indicada",
        )


@router.post("", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MartialClass:
    """Crea una clase ligada a organización, sucursal y disciplina válidas."""

    ensure_can_access_operational_scope(
        current_user,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
    )
    validate_class_links(
        db,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        discipline_id=payload.discipline_id,
    )

    class_obj = MartialClass(**payload.model_dump())
    db.add(class_obj)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la clase por un conflicto de integridad",
        ) from exc

    db.refresh(class_obj)
    return class_obj


@router.get("", response_model=list[ClassRead])
def list_classes(
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    discipline_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[MartialClass]:
    """Lista clases con filtros básicos."""

    organization_id, branch_id = scope_branch_filter(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )
    query = select(MartialClass).order_by(MartialClass.id)

    if organization_id is not None:
        query = query.where(MartialClass.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(MartialClass.branch_id == branch_id)
    if discipline_id is not None:
        query = query.where(MartialClass.discipline_id == discipline_id)
    if is_active is not None:
        query = query.where(MartialClass.is_active == is_active)

    return list(db.scalars(query).all())


@router.get("/{class_id}", response_model=ClassRead)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MartialClass:
    """Devuelve una clase por su id."""

    class_obj = get_class_or_404(db, class_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=class_obj.organization_id,
        branch_id=class_obj.branch_id,
    )
    return class_obj


@router.patch("/{class_id}", response_model=ClassRead)
def update_class(
    class_id: int,
    payload: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MartialClass:
    """Actualiza de forma parcial una clase."""

    class_obj = get_class_or_404(db, class_id)
    changes = payload.model_dump(exclude_unset=True)

    organization_id = changes.get("organization_id", class_obj.organization_id)
    branch_id = changes.get("branch_id", class_obj.branch_id)
    discipline_id = changes.get("discipline_id", class_obj.discipline_id)

    ensure_can_access_operational_scope(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )

    validate_class_links(
        db,
        organization_id=organization_id,
        branch_id=branch_id,
        discipline_id=discipline_id,
    )

    for field_name, value in changes.items():
        setattr(class_obj, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la clase por un conflicto de integridad",
        ) from exc

    db.refresh(class_obj)
    return class_obj


@router.delete("/{class_id}", response_model=MessageResponse)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Realiza borrado lógico desactivando la clase."""

    class_obj = get_class_or_404(db, class_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=class_obj.organization_id,
        branch_id=class_obj.branch_id,
    )
    class_obj.is_active = False
    db.commit()
    return MessageResponse(message="Clase desactivada correctamente")
