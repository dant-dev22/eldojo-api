"""Endpoints CRUD para horarios semanales de clase."""

from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.teaching import ClassSchedule, MartialClass
from app.schemas.class_schedule import (
    ClassScheduleCreate,
    ClassScheduleRead,
    ClassScheduleUpdate,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/class-schedules", tags=["class_schedules"])


def get_schedule_or_404(db: Session, schedule_id: int) -> ClassSchedule:
    """Obtiene un horario existente o corta con 404."""

    schedule = db.get(ClassSchedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado")
    return schedule


def ensure_class_exists(db: Session, class_id: int) -> None:
    """Verifica que la clase exista antes de crear o mover un horario."""

    class_obj = db.get(MartialClass, class_id)
    if class_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")


def ensure_valid_time_range(start_time: time, end_time: time) -> None:
    """Aplica la regla básica de rango horario."""

    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time debe ser menor que end_time",
        )


@router.post("", response_model=ClassScheduleRead, status_code=status.HTTP_201_CREATED)
def create_class_schedule(
    payload: ClassScheduleCreate,
    db: Session = Depends(get_db),
) -> ClassSchedule:
    """Crea un horario semanal para una clase existente."""

    ensure_class_exists(db, payload.class_id)
    ensure_valid_time_range(payload.start_time, payload.end_time)

    schedule = ClassSchedule(**payload.model_dump())
    db.add(schedule)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el horario por un conflicto de integridad",
        ) from exc

    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[ClassScheduleRead])
def list_class_schedules(
    class_id: int | None = Query(default=None, gt=0),
    day_of_week: int | None = Query(default=None, ge=0, le=6),
    db: Session = Depends(get_db),
) -> list[ClassSchedule]:
    """Lista horarios con filtros por clase y día de la semana."""

    query = select(ClassSchedule).order_by(
        ClassSchedule.class_id,
        ClassSchedule.day_of_week,
        ClassSchedule.start_time,
    )

    if class_id is not None:
        query = query.where(ClassSchedule.class_id == class_id)
    if day_of_week is not None:
        query = query.where(ClassSchedule.day_of_week == day_of_week)

    return list(db.scalars(query).all())


@router.get("/{schedule_id}", response_model=ClassScheduleRead)
def get_class_schedule(schedule_id: int, db: Session = Depends(get_db)) -> ClassSchedule:
    """Devuelve un horario por su id."""

    return get_schedule_or_404(db, schedule_id)


@router.patch("/{schedule_id}", response_model=ClassScheduleRead)
def update_class_schedule(
    schedule_id: int,
    payload: ClassScheduleUpdate,
    db: Session = Depends(get_db),
) -> ClassSchedule:
    """Actualiza de forma parcial un horario existente."""

    schedule = get_schedule_or_404(db, schedule_id)
    changes = payload.model_dump(exclude_unset=True)

    class_id = changes.get("class_id", schedule.class_id)
    start_time = changes.get("start_time", schedule.start_time)
    end_time = changes.get("end_time", schedule.end_time)

    ensure_class_exists(db, class_id)
    ensure_valid_time_range(start_time, end_time)

    for field_name, value in changes.items():
        setattr(schedule, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el horario por un conflicto de integridad",
        ) from exc

    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", response_model=MessageResponse)
def delete_class_schedule(schedule_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Elimina físicamente un horario de clase.

    La tabla no tiene soft delete ni bandera activa, así que en esta primera versión
    el borrado es físico.
    """

    schedule = get_schedule_or_404(db, schedule_id)
    db.delete(schedule)
    db.commit()
    return MessageResponse(message="Horario eliminado correctamente")
