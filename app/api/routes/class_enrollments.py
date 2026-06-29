"""Endpoints CRUD para inscripciones de alumnos a clases."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.student import Student
from app.models.teaching import ClassEnrollment, MartialClass
from app.schemas.class_enrollment import (
    ClassEnrollmentCreate,
    ClassEnrollmentRead,
    ClassEnrollmentUpdate,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/class-enrollments", tags=["class_enrollments"])


def get_enrollment_or_404(db: Session, enrollment_id: int) -> ClassEnrollment:
    """Obtiene una inscripción existente o corta con 404."""

    enrollment = db.get(ClassEnrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada")
    return enrollment


def validate_enrollment_links(db: Session, *, student_id: int, class_id: int) -> None:
    """Valida que alumno y clase existan y pertenezcan al mismo alcance."""

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    if student.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede inscribir un alumno eliminado lógicamente",
        )

    class_obj = db.get(MartialClass, class_id)
    if class_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")

    if student.organization_id != class_obj.organization_id or student.branch_id != class_obj.branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El alumno y la clase deben pertenecer a la misma organización y sucursal",
        )


@router.post("", response_model=ClassEnrollmentRead, status_code=status.HTTP_201_CREATED)
def create_class_enrollment(
    payload: ClassEnrollmentCreate,
    db: Session = Depends(get_db),
) -> ClassEnrollment:
    """Crea una inscripción entre un alumno y una clase."""

    validate_enrollment_links(db, student_id=payload.student_id, class_id=payload.class_id)

    enrollment = ClassEnrollment(**payload.model_dump())
    db.add(enrollment)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la inscripción; puede que ya exista para ese alumno y clase",
        ) from exc

    db.refresh(enrollment)
    return enrollment


@router.get("", response_model=list[ClassEnrollmentRead])
def list_class_enrollments(
    student_id: int | None = Query(default=None, gt=0),
    class_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
) -> list[ClassEnrollment]:
    """Lista inscripciones con filtros básicos."""

    query = select(ClassEnrollment).order_by(ClassEnrollment.id)

    if student_id is not None:
        query = query.where(ClassEnrollment.student_id == student_id)
    if class_id is not None:
        query = query.where(ClassEnrollment.class_id == class_id)
    if is_active is not None:
        query = query.where(ClassEnrollment.is_active == is_active)

    return list(db.scalars(query).all())


@router.get("/{enrollment_id}", response_model=ClassEnrollmentRead)
def get_class_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
) -> ClassEnrollment:
    """Devuelve una inscripción por su id."""

    return get_enrollment_or_404(db, enrollment_id)


@router.patch("/{enrollment_id}", response_model=ClassEnrollmentRead)
def update_class_enrollment(
    enrollment_id: int,
    payload: ClassEnrollmentUpdate,
    db: Session = Depends(get_db),
) -> ClassEnrollment:
    """Actualiza de forma parcial una inscripción existente."""

    enrollment = get_enrollment_or_404(db, enrollment_id)
    changes = payload.model_dump(exclude_unset=True)

    student_id = changes.get("student_id", enrollment.student_id)
    class_id = changes.get("class_id", enrollment.class_id)

    validate_enrollment_links(db, student_id=student_id, class_id=class_id)

    for field_name, value in changes.items():
        setattr(enrollment, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la inscripción por un conflicto de integridad",
        ) from exc

    db.refresh(enrollment)
    return enrollment


@router.delete("/{enrollment_id}", response_model=MessageResponse)
def delete_class_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Realiza borrado lógico desactivando la inscripción."""

    enrollment = get_enrollment_or_404(db, enrollment_id)
    enrollment.is_active = False
    db.commit()
    return MessageResponse(message="Inscripción desactivada correctamente")
