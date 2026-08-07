"""Endpoints CRUD para alumnos."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
from app.core.student_codes import build_student_unique_code
from app.db.session import get_db
from app.models.belts import BeltLevel, BeltStripe
from app.models.enums import StudentStatus, UserRole
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate


router = APIRouter(prefix="/students", tags=["students"])


def _student_load_options():
    return (
        selectinload(Student.current_belt_level),
        selectinload(Student.current_stripe),
    )


def get_student_or_404(db: Session, student_id: int) -> Student:
    """Obtiene un alumno existente o corta con 404."""

    student = db.scalar(
        select(Student)
        .where(Student.id == student_id)
        .options(*_student_load_options())
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


def validate_belt_links(
    db: Session,
    *,
    organization_id: int,
    current_belt_level_id: int | None,
    current_stripe_id: int | None,
) -> None:
    """Valida que el nivel de cinta y stripe pertenezcan a la organización y sean coherentes."""

    if current_belt_level_id is None and current_stripe_id is None:
        return

    belt_level: BeltLevel | None = None
    if current_belt_level_id is not None:
        belt_level = db.get(BeltLevel, current_belt_level_id)
        if belt_level is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nivel de cinta no encontrado",
            )
        if belt_level.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El nivel de cinta no pertenece a la organización indicada",
            )

    if current_stripe_id is not None:
        stripe = db.get(BeltStripe, current_stripe_id)
        if stripe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stripe de cinta no encontrado",
            )
        stripe_level = db.get(BeltLevel, stripe.belt_level_id)
        if stripe_level is None or stripe_level.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El stripe de cinta no pertenece a la organización indicada",
            )
        if current_belt_level_id is not None and stripe.belt_level_id != current_belt_level_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El stripe seleccionado no pertenece al nivel de cinta indicado",
            )


def validate_student_links(
    db: Session,
    *,
    organization_id: int,
    branch_id: int,
    user_id: int | None,
    primary_class_id: int | None,
    current_belt_level_id: int | None = None,
    current_stripe_id: int | None = None,
) -> Organization:
    """Valida referencias y coherencia entre organización, sucursal, clase y cinturones."""

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

    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if user.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Solo se puede vincular un usuario con rol student",
            )

    if primary_class_id is not None:
        martial_class = db.get(MartialClass, primary_class_id)
        if martial_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
        if martial_class.organization_id != organization_id or martial_class.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clase principal debe pertenecer a la misma organización y sucursal del alumno",
            )

    validate_belt_links(
        db,
        organization_id=organization_id,
        current_belt_level_id=current_belt_level_id,
        current_stripe_id=current_stripe_id,
    )

    return organization


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Crea un alumno y genera su `unique_code` automáticamente."""

    ensure_can_access_operational_scope(
        current_user,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
    )
    organization = validate_student_links(
        db,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        user_id=payload.user_id,
        primary_class_id=payload.primary_class_id,
        current_belt_level_id=payload.current_belt_level_id,
        current_stripe_id=payload.current_stripe_id,
    )

    student = Student(
        **payload.model_dump(),
        unique_code=build_student_unique_code(db, organization),
    )
    db.add(student)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el alumno por un conflicto de integridad",
        ) from exc

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options())
    )
    return refreshed or student


@router.get("", response_model=list[StudentRead])
def list_students(
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Student]:
    """Lista alumnos con filtros por organización, sucursal, estado y nombre."""

    organization_id, branch_id = scope_branch_filter(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )
    query = (
        select(Student)
        .options(*_student_load_options())
        .order_by(Student.id)
    )

    if organization_id is not None:
        query = query.where(Student.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(Student.branch_id == branch_id)
    if status_filter is not None:
        query = query.where(Student.status == status_filter)
    if search is not None:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Student.first_name.like(search_term),
                Student.last_name.like(search_term),
            )
        )
    if not include_deleted:
        query = query.where(Student.deleted_at.is_(None))

    return list(db.scalars(query).unique().all())


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Devuelve un alumno por su id."""

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    if student.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Actualiza de forma parcial un alumno existente."""

    student = get_student_or_404(db, student_id)
    changes = payload.model_dump(exclude_unset=True)

    organization_id = changes.get("organization_id", student.organization_id)
    branch_id = changes.get("branch_id", student.branch_id)
    user_id = changes.get("user_id", student.user_id)
    primary_class_id = changes.get("primary_class_id", student.primary_class_id)
    current_belt_level_id = changes.get("current_belt_level_id", student.current_belt_level_id)
    current_stripe_id = changes.get("current_stripe_id", student.current_stripe_id)

    ensure_can_access_operational_scope(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )

    validate_student_links(
        db,
        organization_id=organization_id,
        branch_id=branch_id,
        user_id=user_id,
        primary_class_id=primary_class_id,
        current_belt_level_id=current_belt_level_id,
        current_stripe_id=current_stripe_id,
    )

    for field_name, value in changes.items():
        setattr(student, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el alumno por un conflicto de integridad",
        ) from exc

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options())
    )
    return refreshed or student


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Realiza el soft delete del alumno."""

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    student.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    student.status = StudentStatus.INACTIVE
    db.commit()
    return MessageResponse(message="Alumno eliminado lógicamente")
