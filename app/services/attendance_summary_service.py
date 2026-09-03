"""Servicio para calcular agregados de asistencia por alumno."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.models.teaching import Attendance, MartialClass
from app.schemas.attendance import AttendanceSummaryPerClass, StudentAttendanceSummary


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _compute_streak_days(unique_dates_desc: Sequence[date]) -> int:
    """Calcula la racha actual de días consecutivos.

    La cuenta se inicia desde la fecha más reciente (la primera en la lista
    porque está ordenada DESC). Se detiene en cuanto haya una brecha mayor a
    1 día con la fecha anterior.
    """

    if not unique_dates_desc:
        return 0

    streak = 0
    expected_day = unique_dates_desc[0]
    for current_day in unique_dates_desc:
        if current_day == expected_day:
            streak += 1
            expected_day = expected_day - timedelta(days=1)
        else:
            break
    return streak


def _build_by_class_rows(
    db: Session, attendances: Sequence[Attendance]
) -> list[AttendanceSummaryPerClass]:
    """Agrupa asistencias por clase (ignorando class_id null)."""

    counts_by_class_id: dict[int, int] = defaultdict(int)
    for att in attendances:
        if att.class_id is not None:
            counts_by_class_id[att.class_id] += 1

    if not counts_by_class_id:
        return []

    class_ids = list(counts_by_class_id.keys())
    classes = list(
        db.scalars(select(MartialClass).where(MartialClass.id.in_(class_ids))).all()
    )
    class_name_by_id = {cls.id: cls.name for cls in classes}

    rows: list[AttendanceSummaryPerClass] = []
    for class_id, count in sorted(
        counts_by_class_id.items(), key=lambda item: item[1], reverse=True
    ):
        rows.append(
            AttendanceSummaryPerClass(
                class_id=class_id,
                class_name=class_name_by_id.get(class_id, f"Clase #{class_id}"),
                count=count,
            )
        )
    return rows


def build_student_attendance_summary(
    db: Session,
    student: Student,
    *,
    class_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> StudentAttendanceSummary:
    """Calcula los KPIs de asistencia para un alumno determinado."""

    now_utc = _utc_now_naive()
    window_7d_start = now_utc - timedelta(days=7)
    window_30d_start = now_utc - timedelta(days=30)

    predicates = [
        Attendance.student_id == student.id,
        Attendance.branch_id == student.branch_id,
    ]
    if class_id is not None:
        predicates.append(Attendance.class_id == class_id)
    if date_from is not None:
        from_dt = datetime.combine(date_from, datetime.min.time())
        predicates.append(Attendance.check_in_at >= from_dt)
    if date_to is not None:
        to_dt = datetime.combine(date_to, datetime.max.time())
        predicates.append(Attendance.check_in_at <= to_dt)

    stmt = (
        select(Attendance)
        .where(and_(*predicates))
        .order_by(Attendance.check_in_at.asc())
    )
    attendances: list[Attendance] = list(db.scalars(stmt).all())

    total = len(attendances)
    if total == 0:
        return StudentAttendanceSummary(
            student_id=student.id,
            total_attendances=0,
            last_7_days=0,
            last_30_days=0,
            by_class=[],
            first_attendance_at=None,
            last_attendance_at=None,
            streak_days=0,
        )

    last_7 = 0
    last_30 = 0
    unique_dates_desc_set: set[date] = set()
    first_dt = attendances[0].check_in_at
    last_dt = attendances[-1].check_in_at

    for att in attendances:
        check_in = att.check_in_at.replace(tzinfo=None)
        if check_in >= window_7d_start:
            last_7 += 1
        if check_in >= window_30d_start:
            last_30 += 1
        unique_dates_desc_set.add(check_in.date())
        if check_in < first_dt:
            first_dt = check_in
        if check_in > last_dt:
            last_dt = check_in

    unique_dates_desc = sorted(unique_dates_desc_set, reverse=True)
    streak_days = _compute_streak_days(unique_dates_desc)

    by_class_rows = _build_by_class_rows(db, attendances)

    return StudentAttendanceSummary(
        student_id=student.id,
        total_attendances=total,
        last_7_days=last_7,
        last_30_days=last_30,
        by_class=by_class_rows,
        first_attendance_at=first_dt,
        last_attendance_at=last_dt,
        streak_days=streak_days,
    )
