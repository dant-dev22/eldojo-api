"""Endpoints CRUD para asistencia."""

from __future__ import annotations

from datetime import date as _date, datetime, time as _time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
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


def _attendance_list_query_base() -> "select[Attendance]":
    """Construye el SELECT base para listados con relaciones eager-loaded.

    Centraliza el uso de selectinload para evitar duplicación entre el listado
    general y otros endpoints que necesitan devolver AttendanceRead con
    relaciones anidadas.
    """

    return (
        select(Attendance)
        .options(
            selectinload(Attendance.class_obj).selectinload(MartialClass.discipline),
            selectinload(Attendance.student),
        )
        .order_by(Attendance.check_in_at.desc(), Attendance.id.desc())
    )


@router.post("", response_model=AttendanceRead, status_code=status.HTTP_201_CREATED)
def create_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Attendance:
    """Crea un registro de asistencia."""

    student = db.get(Student, payload.student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=payload.branch_id,
    )
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
    date_from: _date | None = Query(default=None, description="Fecha mínima de check-in (inclusiva)"),
    date_to: _date | None = Query(default=None, description="Fecha máxima de check-in (inclusiva)"),
    limit: int = Query(default=100, ge=1, le=500, description="Cantidad máxima de registros a devolver"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento inicial para paginación"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Attendance]:
    """Lista asistencias con filtros básicos, paginación y relaciones anidadas."""

    scoped_organization_id, scoped_branch_id = scope_branch_filter(
        current_user,
        organization_id=None,
        branch_id=branch_id,
    )
    query = _attendance_list_query_base()
    if scoped_organization_id is not None:
        query = query.join(Branch, Branch.id == Attendance.branch_id).where(
            Branch.organization_id == scoped_organization_id
        )

    if student_id is not None:
        query = query.where(Attendance.student_id == student_id)
    if scoped_branch_id is not None:
        query = query.where(Attendance.branch_id == scoped_branch_id)
    if class_id is not None:
        query = query.where(Attendance.class_id == class_id)
    if method is not None:
        query = query.where(Attendance.method == method)
    if date_from is not None:
        start_dt = datetime.combine(date_from, _time.min).replace(tzinfo=None)
        query = query.where(Attendance.check_in_at >= start_dt)
    if date_to is not None:
        end_dt = datetime.combine(date_to, _time.max).replace(tzinfo=None)
        query = query.where(Attendance.check_in_at <= end_dt)

    query = query.limit(limit).offset(offset)
    return list(db.scalars(query).all())


@router.get("/{attendance_id}", response_model=AttendanceRead)
def get_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Attendance:
    """Devuelve una asistencia por su id."""

    attendance = get_attendance_or_404(db, attendance_id)
    student = db.get(Student, attendance.student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=attendance.branch_id,
    )
    return attendance


@router.patch("/{attendance_id}", response_model=AttendanceRead)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Attendance:
    """Actualiza de forma parcial un registro de asistencia."""

    attendance = get_attendance_or_404(db, attendance_id)
    changes = payload.model_dump(exclude_unset=True)

    student_id = changes.get("student_id", attendance.student_id)
    branch_id = changes.get("branch_id", attendance.branch_id)
    class_id = changes.get("class_id", attendance.class_id)
    registered_by = changes.get("registered_by", attendance.registered_by)

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=branch_id,
    )

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
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina físicamente una asistencia.

    La tabla no tiene soft delete ni bandera activa, así que esta primera versión
    usa borrado físico.
    """

    attendance = get_attendance_or_404(db, attendance_id)
    student = db.get(Student, attendance.student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=attendance.branch_id,
    )
    db.delete(attendance)
    db.commit()
    return MessageResponse(message="Asistencia eliminada correctamente")
