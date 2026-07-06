"""Endpoints basicos para disciplinas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_manage_organization, scope_organization_filter
from app.db.session import get_db
from app.models.curriculum import Discipline
from app.models.organization import Organization
from app.models.user import User
from app.schemas.discipline import DisciplineCreate, DisciplineRead


router = APIRouter(prefix="/disciplines", tags=["disciplines"])


def ensure_organization_exists(db: Session, organization_id: int) -> None:
    """Valida que la organizacion exista antes de crear la disciplina."""

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizacion no encontrada")


@router.post("", response_model=DisciplineRead, status_code=status.HTTP_201_CREATED)
def create_discipline(
    payload: DisciplineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Discipline:
    """Crea una disciplina disponible para la organizacion."""

    ensure_can_manage_organization(current_user, payload.organization_id)
    ensure_organization_exists(db, payload.organization_id)

    existing_discipline = db.scalar(
        select(Discipline).where(
            Discipline.organization_id == payload.organization_id,
            Discipline.name == payload.name,
        )
    )
    if existing_discipline is not None:
        return existing_discipline

    discipline = Discipline(**payload.model_dump())
    db.add(discipline)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la disciplina por un conflicto de integridad",
        ) from exc

    db.refresh(discipline)
    return discipline


@router.get("", response_model=list[DisciplineRead])
def list_disciplines(
    organization_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Discipline]:
    """Lista disciplinas visibles dentro del alcance del usuario."""

    scoped_organization_id = scope_organization_filter(current_user, organization_id)
    query = select(Discipline).order_by(Discipline.name, Discipline.id)

    if scoped_organization_id is not None:
        query = query.where(Discipline.organization_id == scoped_organization_id)
    if is_active is not None:
        query = query.where(Discipline.is_active == is_active)

    return list(db.scalars(query).all())
