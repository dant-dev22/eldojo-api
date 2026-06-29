"""Endpoints CRUD para asistencia."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import AttendanceMethod, UserRole
from app.models.organization import Branch
from app.models.student import Student
from app.models.teaching import Attendance, MartialClass
from app.models.user import User
from app.schemas.attendance import AttendanceCreate, AttendanceRead, AttendanceUpdate
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/attendance", tags=["attendance"])


def get_attendance_or_404(db: Session, attendance_id: int) -> Attendance:
    """Obtiene una asistencia existente o corta con 404."""

    attendance = db.get(Attendance, attendance_id)
    if attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asistencia no encontrada")
    return attendance


def validate_attendance_links(
    db: Session,
    *,
    student_id: int,
    branch_id: int,
    class_id: int | None,
    registered_by: int | None,
) -> None:
    """Valida coherencia entre alumno, sucursal, clase y registrador."""

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    if student.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede registrar asistencia para un alumno eliminado lógicamente",
        )
    if student.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La sucursal de asistencia debe coincidir con la sucursal del alumno",
        )

    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")

    if class_id is not None:
        class_obj = db.get(MartialClass, class_id)
        if class_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
        if class_obj.branch_id != branch_id or class_obj.organization_id != student.organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clase debe pertenecer a la misma organización y sucursal del alumno",
            )

    if registered_by is not None:
        user = db.get(User, registered_by)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario registrador no encontrado")
        if user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="registered_by no puede apuntar a un usuario con rol student",
            )


@router.post("", response_model=AttendanceRead, status_code=status.HTTP_201_CREATED)
def create_attendance(payload: AttendanceCreate, db: Session = Depends(get_db)) -> Attendance:
    """Crea un registro de asistencia."""

    validate_attendance_links(
        db,
        student_id=payload.student_id,
        branch_id=payload.branch_id,
        class_id=payload.class_id,
        registered_by=payload.registered_by,
    )

    attendance = Attendance(**payload.model_dump())
    db.add(attendance)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la asistencia por un conflicto de integridad",
        ) from exc

    db.refresh(attendance)
    return attendance


@router.get("", response_model=list[AttendanceRead])
def list_attendance(
    student_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    class_id: int | None = Query(default=None, gt=0),
    method: AttendanceMethod | None = None,
    db: Session = Depends(get_db),
) -> list[Attendance]:
    """Lista asistencias con filtros básicos."""

    query = select(Attendance).order_by(Attendance.check_in_at.desc(), Attendance.id.desc())

    if student_id is not None:
        query = query.where(Attendance.student_id == student_id)
    if branch_id is not None:
        query = query.where(Attendance.branch_id == branch_id)
    if class_id is not None:
        query = query.where(Attendance.class_id == class_id)
    if method is not None:
        query = query.where(Attendance.method == method)

    return list(db.scalars(query).all())


@router.get("/{attendance_id}", response_model=AttendanceRead)
def get_attendance(attendance_id: int, db: Session = Depends(get_db)) -> Attendance:
    """Devuelve una asistencia por su id."""

    return get_attendance_or_404(db, attendance_id)


@router.patch("/{attendance_id}", response_model=AttendanceRead)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    db: Session = Depends(get_db),
) -> Attendance:
    """Actualiza de forma parcial un registro de asistencia."""

    attendance = get_attendance_or_404(db, attendance_id)
    changes = payload.model_dump(exclude_unset=True)

    student_id = changes.get("student_id", attendance.student_id)
    branch_id = changes.get("branch_id", attendance.branch_id)
    class_id = changes.get("class_id", attendance.class_id)
    registered_by = changes.get("registered_by", attendance.registered_by)

    validate_attendance_links(
        db,
        student_id=student_id,
        branch_id=branch_id,
        class_id=class_id,
        registered_by=registered_by,
    )

    for field_name, value in changes.items():
        setattr(attendance, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar la asistencia por un conflicto de integridad",
        ) from exc

    db.refresh(attendance)
    return attendance


@router.delete("/{attendance_id}", response_model=MessageResponse)
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Elimina físicamente una asistencia.

    La tabla no tiene soft delete ni bandera activa, así que esta primera versión
    usa borrado físico.
    """

    attendance = get_attendance_or_404(db, attendance_id)
    db.delete(attendance)
    db.commit()
    return MessageResponse(message="Asistencia eliminada correctamente")
