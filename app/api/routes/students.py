"""Endpoints CRUD para alumnos."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.student_codes import build_student_unique_code
from app.db.session import get_db
from app.models.enums import StudentStatus, UserRole
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate


router = APIRouter(prefix="/students", tags=["students"])


def get_student_or_404(db: Session, student_id: int) -> Student:
    """Obtiene un alumno existente o corta con 404."""

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


def validate_student_links(
    db: Session,
    *,
    organization_id: int,
    branch_id: int,
    user_id: int | None,
    primary_class_id: int | None,
) -> Organization:
    """Valida referencias y coherencia entre organización, sucursal y clase."""

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

    return organization


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    """Crea un alumno y genera su `unique_code` automáticamente."""

    organization = validate_student_links(
        db,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        user_id=payload.user_id,
        primary_class_id=payload.primary_class_id,
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

    db.refresh(student)
    return student


@router.get("", response_model=list[StudentRead])
def list_students(
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[Student]:
    """Lista alumnos con filtros por organización, sucursal y estado."""

    query = select(Student).order_by(Student.id)

    if organization_id is not None:
        query = query.where(Student.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(Student.branch_id == branch_id)
    if status_filter is not None:
        query = query.where(Student.status == status_filter)
    if not include_deleted:
        query = query.where(Student.deleted_at.is_(None))

    return list(db.scalars(query).all())


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> Student:
    """Devuelve un alumno por su id."""

    student = get_student_or_404(db, student_id)
    if student.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
) -> Student:
    """Actualiza de forma parcial un alumno existente."""

    student = get_student_or_404(db, student_id)
    changes = payload.model_dump(exclude_unset=True)

    organization_id = changes.get("organization_id", student.organization_id)
    branch_id = changes.get("branch_id", student.branch_id)
    user_id = changes.get("user_id", student.user_id)
    primary_class_id = changes.get("primary_class_id", student.primary_class_id)

    validate_student_links(
        db,
        organization_id=organization_id,
        branch_id=branch_id,
        user_id=user_id,
        primary_class_id=primary_class_id,
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

    db.refresh(student)
    return student


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(student_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Realiza el soft delete del alumno."""

    student = get_student_or_404(db, student_id)
    student.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    student.status = StudentStatus.INACTIVE
    db.commit()
    return MessageResponse(message="Alumno eliminado lógicamente")
