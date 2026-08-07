"""Endpoints CRUD para catálogo de cinturones, stripes e historial de promociones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_manage_organization, scope_organization_filter
from app.db.session import get_db
from app.models.belts import BeltLevel, BeltStripe, StudentBeltHistory
from app.models.organization import Organization
from app.models.student import Student
from app.models.user import User
from app.schemas.belt import (
    BeltLevelCreate,
    BeltLevelRead,
    BeltLevelUpdate,
    BeltStripeCreate,
    BeltStripeRead,
    BeltStripeUpdate,
    StudentBeltHistoryCreate,
    StudentBeltHistoryRead,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/belts", tags=["belts"])


def _ensure_organization(db: Session, organization_id: int) -> None:
    org = db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organización no encontrada")


def _get_belt_level_or_404(db: Session, belt_level_id: int) -> BeltLevel:
    belt = db.get(BeltLevel, belt_level_id)
    if belt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nivel de cinta no encontrado")
    return belt


def _get_belt_stripe_or_404(db: Session, stripe_id: int) -> BeltStripe:
    stripe = db.get(BeltStripe, stripe_id)
    if stripe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe de cinta no encontrado")
    return stripe


def _get_student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


def _validate_stripe_belongs_to_level(stripe: BeltStripe, belt_level_id: int | None) -> None:
    if belt_level_id is not None and stripe.belt_level_id != belt_level_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El stripe seleccionado no pertenece al nivel de cinta indicado",
        )


# ---------------- BeltLevel endpoints ----------------

@router.post("/levels", response_model=BeltLevelRead, status_code=status.HTTP_201_CREATED)
def create_belt_level(
    payload: BeltLevelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltLevel:
    """Crea un nuevo nivel de cinta para una organización."""

    ensure_can_manage_organization(current_user, payload.organization_id)
    _ensure_organization(db, payload.organization_id)

    belt_level = BeltLevel(**payload.model_dump())
    db.add(belt_level)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el nivel de cinta (nombre o índice duplicado en la organización)",
        ) from exc

    db.refresh(belt_level)
    return belt_level


@router.get("/levels", response_model=list[BeltLevelRead])
def list_belt_levels(
    organization_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = Query(default=None),
    include_stripes: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[BeltLevel]:
    """Lista niveles de cinta (con sus stripes) visibles dentro del alcance del usuario."""

    scoped_organization_id = scope_organization_filter(current_user, organization_id)
    query = select(BeltLevel).order_by(BeltLevel.order_index, BeltLevel.id)

    if include_stripes:
        query = query.options(selectinload(BeltLevel.stripes))

    if scoped_organization_id is not None:
        query = query.where(BeltLevel.organization_id == scoped_organization_id)
    if is_active is not None:
        query = query.where(BeltLevel.is_active == is_active)

    result = list(db.scalars(query).unique().all())
    if include_stripes:
        for belt in result:
            belt.stripes.sort(key=lambda s: (s.order_index, s.id))
    return result


@router.get("/levels/{belt_level_id}", response_model=BeltLevelRead)
def get_belt_level(
    belt_level_id: int,
    include_stripes: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltLevel:
    """Obtiene un nivel de cinta por su id."""

    stmt = select(BeltLevel).where(BeltLevel.id == belt_level_id)
    if include_stripes:
        stmt = stmt.options(selectinload(BeltLevel.stripes))

    belt_level = db.scalar(stmt)
    if belt_level is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nivel de cinta no encontrado")

    ensure_can_manage_organization(current_user, belt_level.organization_id)
    if include_stripes:
        belt_level.stripes.sort(key=lambda s: (s.order_index, s.id))
    return belt_level


@router.patch("/levels/{belt_level_id}", response_model=BeltLevelRead)
def update_belt_level(
    belt_level_id: int,
    payload: BeltLevelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltLevel:
    """Actualiza parcialmente un nivel de cinta."""

    belt_level = _get_belt_level_or_404(db, belt_level_id)
    ensure_can_manage_organization(current_user, belt_level.organization_id)

    changes = payload.model_dump(exclude_unset=True)
    new_organization_id = changes.get("organization_id", belt_level.organization_id)
    if new_organization_id != belt_level.organization_id:
        ensure_can_manage_organization(current_user, new_organization_id)
        _ensure_organization(db, new_organization_id)

    for field_name, value in changes.items():
        setattr(belt_level, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el nivel de cinta por conflicto de integridad",
        ) from exc

    db.refresh(belt_level)
    return belt_level


@router.delete("/levels/{belt_level_id}", response_model=MessageResponse)
def delete_belt_level(
    belt_level_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina un nivel de cinta (solo si no está en uso por alumnos ni historial)."""

    belt_level = _get_belt_level_or_404(db, belt_level_id)
    ensure_can_manage_organization(current_user, belt_level.organization_id)

    try:
        db.delete(belt_level)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: el nivel de cinta está referenciado por alumnos o su historial",
        ) from exc

    return MessageResponse(message="Nivel de cinta eliminado")


# ---------------- BeltStripe endpoints ----------------

@router.post("/stripes", response_model=BeltStripeRead, status_code=status.HTTP_201_CREATED)
def create_belt_stripe(
    payload: BeltStripeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltStripe:
    """Crea un nuevo stripe/punto asociado a un nivel de cinta."""

    belt_level = _get_belt_level_or_404(db, payload.belt_level_id)
    ensure_can_manage_organization(current_user, belt_level.organization_id)

    stripe = BeltStripe(**payload.model_dump())
    db.add(stripe)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el stripe (nombre o índice duplicado en el nivel)",
        ) from exc

    db.refresh(stripe)
    return stripe


@router.get("/stripes", response_model=list[BeltStripeRead])
def list_belt_stripes(
    belt_level_id: int | None = Query(default=None, gt=0),
    organization_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[BeltStripe]:
    """Lista stripes visibles por nivel de cinta y/o organización."""

    scoped_organization_id = scope_organization_filter(current_user, organization_id)
    query = select(BeltStripe).order_by(BeltStripe.order_index, BeltStripe.id)

    if belt_level_id is not None:
        query = query.where(BeltStripe.belt_level_id == belt_level_id)
    if scoped_organization_id is not None:
        query = query.join(BeltLevel).where(BeltLevel.organization_id == scoped_organization_id)
    if is_active is not None:
        query = query.where(BeltStripe.is_active == is_active)

    return list(db.scalars(query).all())


@router.get("/stripes/{stripe_id}", response_model=BeltStripeRead)
def get_belt_stripe(
    stripe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltStripe:
    """Obtiene un stripe de cinta por su id."""

    stripe = _get_belt_stripe_or_404(db, stripe_id)
    belt_level = _get_belt_level_or_404(db, stripe.belt_level_id)
    ensure_can_manage_organization(current_user, belt_level.organization_id)
    return stripe


@router.patch("/stripes/{stripe_id}", response_model=BeltStripeRead)
def update_belt_stripe(
    stripe_id: int,
    payload: BeltStripeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> BeltStripe:
    """Actualiza parcialmente un stripe."""

    stripe = _get_belt_stripe_or_404(db, stripe_id)
    old_level = _get_belt_level_or_404(db, stripe.belt_level_id)
    ensure_can_manage_organization(current_user, old_level.organization_id)

    changes = payload.model_dump(exclude_unset=True)
    new_level_id = changes.get("belt_level_id", stripe.belt_level_id)
    if new_level_id != stripe.belt_level_id:
        new_level = _get_belt_level_or_404(db, new_level_id)
        ensure_can_manage_organization(current_user, new_level.organization_id)

    for field_name, value in changes.items():
        setattr(stripe, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el stripe por conflicto de integridad",
        ) from exc

    db.refresh(stripe)
    return stripe


@router.delete("/stripes/{stripe_id}", response_model=MessageResponse)
def delete_belt_stripe(
    stripe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina un stripe (solo si no está en uso)."""

    stripe = _get_belt_stripe_or_404(db, stripe_id)
    belt_level = _get_belt_level_or_404(db, stripe.belt_level_id)
    ensure_can_manage_organization(current_user, belt_level.organization_id)

    try:
        db.delete(stripe)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar: el stripe está en uso por un alumno o su historial",
        ) from exc

    return MessageResponse(message="Stripe eliminado")


# ---------------- StudentBeltHistory endpoints ----------------

@router.post("/history", response_model=StudentBeltHistoryRead, status_code=status.HTTP_201_CREATED)
def create_student_belt_history(
    payload: StudentBeltHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentBeltHistory:
    """Registra una promoción / cambio de cinta de un alumno.

    Si `update_student_current` es True (default), actualiza automáticamente
    `current_belt_level_id` y `current_stripe_id` del alumno.
    """

    student = _get_student_or_404(db, payload.student_id)
    from app.core.authorization import ensure_can_access_operational_scope
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    belt_level = _get_belt_level_or_404(db, payload.belt_level_id)
    if belt_level.organization_id != student.organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nivel de cinta no pertenece a la misma organización que el alumno",
        )

    stripe: BeltStripe | None = None
    if payload.stripe_id is not None:
        stripe = _get_belt_stripe_or_404(db, payload.stripe_id)
        _validate_stripe_belongs_to_level(stripe, payload.belt_level_id)

    if payload.awarded_by_user_id is not None:
        awarded_by = db.get(User, payload.awarded_by_user_id)
        if awarded_by is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario que otorgó la cinta no encontrado",
            )

    history_payload = payload.model_dump(exclude={"update_student_current"})
    history = StudentBeltHistory(**history_payload)
    db.add(history)

    if payload.update_student_current:
        student.current_belt_level_id = payload.belt_level_id
        student.current_stripe_id = payload.stripe_id

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible registrar el cambio de cinta",
        ) from exc

    db.refresh(history)
    return history


@router.get("/history", response_model=list[StudentBeltHistoryRead])
def list_student_belt_history(
    student_id: int | None = Query(default=None, gt=0),
    organization_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[StudentBeltHistory]:
    """Lista historial de promociones, filtrado opcionalmente por alumno u organización."""

    scoped_org = scope_organization_filter(current_user, organization_id)
    query = (
        select(StudentBeltHistory)
        .options(
            selectinload(StudentBeltHistory.belt_level),
            selectinload(StudentBeltHistory.stripe),
        )
        .order_by(StudentBeltHistory.awarded_at.desc(), StudentBeltHistory.id.desc())
    )

    if student_id is not None:
        student = _get_student_or_404(db, student_id)
        from app.core.authorization import ensure_can_access_operational_scope
        ensure_can_access_operational_scope(
            current_user,
            organization_id=student.organization_id,
            branch_id=student.branch_id,
        )
        query = query.where(StudentBeltHistory.student_id == student_id)
    elif scoped_org is not None:
        query = query.join(Student).where(Student.organization_id == scoped_org)

    return list(db.scalars(query).unique().all())
