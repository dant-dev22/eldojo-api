"""Endpoints CRUD para registros deportivos (peleas) de alumnos.

Cada alumno puede tener una colección de victorias, empates o derrotas
registradas individualmente con nombre del rival (≤50 chars) y fecha.

Los totales agregados rd_victorias / rd_empates / rd_derrotas en la tabla
students se mantienen automáticamente en la capa de servicio
(app.services.fight_record_sync) de forma atómica y transaccional en
los endpoints de escritura (POST / PATCH / DELETE).
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope
from app.db.session import get_db
from app.models.fight_record import FightRecordType, StudentFightRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.fight_record import (
    StudentFightRecordCreate,
    StudentFightRecordRead,
    StudentFightRecordUpdate,
)
from app.services.fight_record_sync import (
    sync_student_fight_totals_after_create,
    sync_student_fight_totals_after_soft_delete,
    sync_student_fight_totals_after_update,
)

router = APIRouter(prefix="/fight-records", tags=["fight-records"])


def _get_student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alumno no encontrado",
        )
    return student


def _get_record_or_404(db: Session, record_id: int) -> StudentFightRecord:
    record = db.get(StudentFightRecord, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registro deportivo no encontrado",
        )
    return record


@router.post("", response_model=StudentFightRecordRead, status_code=status.HTTP_201_CREATED)
def create_fight_record(
    payload: StudentFightRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentFightRecord:
    """Registra un nuevo encuentro deportivo para un alumno."""

    student = _get_student_or_404(db, payload.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    record = StudentFightRecord(
        student_id=payload.student_id,
        record_type=payload.record_type,
        opponent_name=payload.opponent_name,
        fight_date=payload.fight_date,
    )
    db.add(record)
    db.flush()

    sync_student_fight_totals_after_create(
        db,
        student_id=record.student_id,
        new_record_type=record.record_type,
    )
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[StudentFightRecordRead])
def list_fight_records(
    student_id: int = Query(..., gt=0),
    record_type: FightRecordType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[StudentFightRecord]:
    """Lista los registros deportivos de un alumno (más recientes primero)."""

    student = _get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    query = (
        select(StudentFightRecord)
        .where(
            StudentFightRecord.student_id == student_id,
            StudentFightRecord.deleted_at.is_(None),
        )
        .order_by(StudentFightRecord.fight_date.desc(), StudentFightRecord.id.desc())
    )

    if record_type is not None:
        query = query.where(StudentFightRecord.record_type == record_type)
    if date_from is not None:
        query = query.where(StudentFightRecord.fight_date >= date_from)
    if date_to is not None:
        query = query.where(StudentFightRecord.fight_date <= date_to)

    return list(db.scalars(query).all())


@router.get("/{record_id}", response_model=StudentFightRecordRead)
def get_fight_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentFightRecord:
    """Obtiene un registro deportivo por id."""

    record = _get_record_or_404(db, record_id)
    student = _get_student_or_404(db, record.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    return record


@router.patch("/{record_id}", response_model=StudentFightRecordRead)
def update_fight_record(
    record_id: int,
    payload: StudentFightRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentFightRecord:
    """Actualiza parcialmente un registro deportivo (tipo, rival o fecha)."""

    record = _get_record_or_404(db, record_id)
    student = _get_student_or_404(db, record.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    old_student_id = record.student_id
    old_record_type = record.record_type

    changes = payload.model_dump(exclude_unset=True)
    for field_name, value in changes.items():
        setattr(record, field_name, value)

    db.flush()

    if "record_type" in changes or "student_id" in changes:
        sync_student_fight_totals_after_update(
            db,
            old_student_id=old_student_id,
            new_student_id=record.student_id,
            old_record_type=old_record_type,
            new_record_type=record.record_type,
        )

    db.commit()
    db.refresh(record)
    return record


@router.delete("/{record_id}", response_model=MessageResponse)
def delete_fight_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina (soft delete) un registro deportivo."""

    record = _get_record_or_404(db, record_id)
    student = _get_student_or_404(db, record.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    old_student_id = record.student_id
    old_record_type = record.record_type

    record.deleted_at = datetime.utcnow()
    db.flush()

    sync_student_fight_totals_after_soft_delete(
        db,
        student_id=old_student_id,
        old_record_type=old_record_type,
    )
    db.commit()
    return MessageResponse(message="Registro deportivo eliminado")
