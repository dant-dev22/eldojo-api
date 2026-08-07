"""Modelo ORM para registros de peleas / encuentros deportivos de un alumno.

Cada registro individual almacena:
- tipo de resultado (victoria / empate / derrota)
- nombre y apellido del rival (máx 50 caracteres)
- fecha del encuentro
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FightRecordType(str, Enum):
    VICTORY = "victoria"
    DRAW = "empate"
    LOSS = "derrota"


class StudentFightRecord(Base):
    """Registro individual de un encuentro deportivo del alumno."""

    __tablename__ = "student_fight_records"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(TRIM(opponent_name)) > 0",
            name="chk_student_fight_records_opponent_not_empty",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_type: Mapped[FightRecordType] = mapped_column(
        SQLEnum(FightRecordType, name="fight_record_type_enum"),
        nullable=False,
        index=True,
    )
    opponent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    fight_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    student = relationship("Student", back_populates="fight_records")
