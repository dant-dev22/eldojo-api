"""Endpoints CRUD para el sistema de trayectoria / recuerdos de alumnos."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_organization_filter
from app.db.session import get_db
from app.models.organization import Organization
from app.models.student import Student
from app.models.trajectory import TrajectoryEvent
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.trajectory import (
    StudentTrajectorySummary,
    TrajectoryEventCreate,
    TrajectoryEventRead,
    TrajectoryEventUpdate,
)


router = APIRouter(prefix="/trajectory", tags=["trajectory"])


def _get_student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alumno no encontrado",
        )
    return student


def _get_event_or_404(db: Session, event_id: int) -> TrajectoryEvent:
    event = db.get(TrajectoryEvent, event_id)
    if event is None or event.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suceso de trayectoria no encontrado",
        )
    return event


# ---------------- Event endpoints ----------------


@router.post("/events", response_model=TrajectoryEventRead, status_code=status.HTTP_201_CREATED)
def create_trajectory_event(
    payload: TrajectoryEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> TrajectoryEvent:
    """Registra un nuevo suceso / recuerdo en la trayectoria de un alumno."""

    student = _get_student_or_404(db, payload.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    event = TrajectoryEvent(
        student_id=payload.student_id,
        organization_id=student.organization_id,
        event_date=payload.event_date,
        content=payload.content,
        created_by_user_id=current_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/events", response_model=list[TrajectoryEventRead])
def list_trajectory_events(
    student_id: int | None = Query(default=None, gt=0),
    organization_id: int | None = Query(default=None, gt=0),
    event_date_from: date | None = Query(default=None),
    event_date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[TrajectoryEvent]:
    """Lista sucesos de trayectoria, filtrados opcionalmente por alumno, organización y/o rango de fechas."""

    scoped_org = scope_organization_filter(current_user, organization_id)

    if student_id is not None:
        student = _get_student_or_404(db, student_id)
        ensure_can_access_operational_scope(
            current_user,
            organization_id=student.organization_id,
            branch_id=student.branch_id,
        )

    query = (
        select(TrajectoryEvent)
        .where(TrajectoryEvent.deleted_at.is_(None))
        .order_by(TrajectoryEvent.event_date.desc(), TrajectoryEvent.id.desc())
    )

    if student_id is not None:
        query = query.where(TrajectoryEvent.student_id == student_id)
    elif scoped_org is not None:
        query = query.where(TrajectoryEvent.organization_id == scoped_org)

    if event_date_from is not None:
        query = query.where(TrajectoryEvent.event_date >= event_date_from)
    if event_date_to is not None:
        query = query.where(TrajectoryEvent.event_date <= event_date_to)

    return list(db.scalars(query).all())


@router.get("/events/{event_id}", response_model=TrajectoryEventRead)
def get_trajectory_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> TrajectoryEvent:
    """Obtiene un suceso de trayectoria por su id."""

    event = _get_event_or_404(db, event_id)
    student = _get_student_or_404(db, event.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    return event


@router.patch("/events/{event_id}", response_model=TrajectoryEventRead)
def update_trajectory_event(
    event_id: int,
    payload: TrajectoryEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> TrajectoryEvent:
    """Actualiza parcialmente un suceso de trayectoria."""

    event = _get_event_or_404(db, event_id)
    student = _get_student_or_404(db, event.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    changes = payload.model_dump(exclude_unset=True)
    for field_name, value in changes.items():
        setattr(event, field_name, value)

    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}", response_model=MessageResponse)
def delete_trajectory_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Elimina (soft delete) un suceso de trayectoria."""

    from datetime import datetime

    event = _get_event_or_404(db, event_id)
    student = _get_student_or_404(db, event.student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    event.deleted_at = datetime.utcnow()
    db.commit()
    return MessageResponse(message="Suceso eliminado de la trayectoria")


# ---------------- Summary endpoints ----------------


@router.get("/summary/by-student", response_model=list[StudentTrajectorySummary])
def list_students_trajectory_summary(
    student_ids: list[int] | None = Query(default=None),
    organization_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    """Devuelve un resumen agregado (conteos, fechas) por cada alumno solicitado."""

    scoped_org = scope_organization_filter(current_user, organization_id)

    base_query = (
        select(
            TrajectoryEvent.student_id.label("student_id"),
            func.count(TrajectoryEvent.id).label("total_events"),
            func.min(TrajectoryEvent.event_date).label("first_event_date"),
            func.max(TrajectoryEvent.event_date).label("last_event_date"),
        )
        .where(TrajectoryEvent.deleted_at.is_(None))
        .group_by(TrajectoryEvent.student_id)
    )

    if scoped_org is not None:
        base_query = base_query.where(TrajectoryEvent.organization_id == scoped_org)
    if student_ids:
        base_query = base_query.where(TrajectoryEvent.student_id.in_(student_ids))

    rows = db.execute(base_query).all()
    summaries: list[StudentTrajectorySummary] = []
    for row in rows:
        row_dict = row._asdict()
        summaries.append(StudentTrajectorySummary(**row_dict))
    return summaries
