"""Sincroniza rd_victorias / rd_empates / rd_derrotas en students.

Reemplaza a los triggers SQL originales (no viables en entornos managed con
binlog + sin SUPER), y además CORRIGE la divergencia que habría en soft
delete (el endpoint DELETE marca deleted_at, no borra físicamente).

Todas las operaciones son atómicas y se ejecutan DENTRO de la misma
transacción del ORM (Session.flush() + un solo commit por request).
"""

from __future__ import annotations

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.fight_record import FightRecordType, StudentFightRecord
from app.models.student import Student


def _field_for(record_type: FightRecordType | str) -> str:
    rt = FightRecordType(record_type) if isinstance(record_type, str) else record_type
    if rt is FightRecordType.VICTORY:
        return "rd_victorias"
    if rt is FightRecordType.DRAW:
        return "rd_empates"
    # LOSS
    return "rd_derrotas"


def _increment(db: Session, student_id: int, record_type: FightRecordType | str, delta: int) -> None:
    """Suma o resta `delta` (±1) en el contador correcto del alumno.

    Usa ``field = GREATEST(field + delta, 0)`` para que el contador nunca
    quede negativo (igual que el trigger original hacía con GREATEST).
    """

    field = _field_for(record_type)
    sign = "+" if delta >= 0 else "-"
    abs_delta = abs(delta)
    stmt = (
        f"UPDATE students "
        f"   SET {field} = GREATEST({field} {sign} {abs_delta}, 0) "
        f" WHERE id = :student_id"
    )
    db.execute(statement=stmt, params={"student_id": student_id})


def _get_for_update(db: Session, student_id: int) -> Student:
    row = db.get(Student, student_id)
    if row is None:
        raise ValueError(f"Student id={student_id} not found while syncing fight totals")
    return row


def sync_student_fight_totals_after_create(
    db: Session,
    student_id: int,
    new_record_type: FightRecordType | str,
) -> None:
    """Después de INSERTAR un registro → suma 1 al bucket nuevo."""

    _get_for_update(db, student_id)
    _increment(db, student_id, new_record_type, +1)
    db.flush()


def sync_student_fight_totals_after_update(
    db: Session,
    *,
    old_student_id: int,
    new_student_id: int,
    old_record_type: FightRecordType | str,
    new_record_type: FightRecordType | str,
) -> None:
    """Después de ACTUALIZAR un registro.

    - Resta 1 del (tipo anterior, alumno anterior).
    - Suma 1 al   (tipo nuevo,     alumno nuevo).

    Si alumno o tipo no cambiaron, se cancelan automáticamente los cambios
    netos (restar 1 + sumar 1 = 0 en el mismo bucket).
    """

    _get_for_update(db, old_student_id)
    if new_student_id != old_student_id:
        _get_for_update(db, new_student_id)

    _increment(db, old_student_id, old_record_type, -1)
    _increment(db, new_student_id, new_record_type, +1)
    db.flush()


def sync_student_fight_totals_after_soft_delete(
    db: Session,
    student_id: int,
    old_record_type: FightRecordType | str,
) -> None:
    """Después de SOFT DELETE (deleted_at se asigna) → resta 1.

    A diferencia del trigger AFTER DELETE físico original, éste sí corre
    cuando el endpoint DELETE marca el registro como borrado lógico.
    """

    _get_for_update(db, student_id)
    _increment(db, student_id, old_record_type, -1)
    db.flush()


def recompute_student_fight_totals(db: Session, student_id: int) -> tuple[int, int, int]:
    """Reconciliación: cuenta registros NO borrados y escribe totales reales.

    Útil después de carga masiva, imports, o cuando un operario modificó
    manualmente la tabla por fuera de la API.

    Devuelve (victorias, empates, derrotas) calculados.
    """

    stmt = select(
        func.sum(case((StudentFightRecord.record_type == FightRecordType.VICTORY, 1), else_=0)).label("v"),
        func.sum(case((StudentFightRecord.record_type == FightRecordType.DRAW, 1), else_=0)).label("e"),
        func.sum(case((StudentFightRecord.record_type == FightRecordType.LOSS, 1), else_=0)).label("d"),
    ).where(
        and_(
            StudentFightRecord.student_id == student_id,
            StudentFightRecord.deleted_at.is_(None),
        )
    )
    row = db.execute(stmt).one_or_none()
    v = int(row.v or 0) if row is not None else 0
    e = int(row.e or 0) if row is not None else 0
    d = int(row.d or 0) if row is not None else 0

    student = _get_for_update(db, student_id)
    student.rd_victorias = v
    student.rd_empates = e
    student.rd_derrotas = d
    db.flush()
    return v, e, d
