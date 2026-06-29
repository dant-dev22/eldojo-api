"""Enums usados por el backend para leer y escribir los ENUM nativos de MySQL."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SqlEnum


class UserRole(str, Enum):
    """Roles soportados en la fase inicial del sistema."""

    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    BRANCH_ADMIN = "branch_admin"
    STUDENT = "student"


class PaymentStatus(str, Enum):
    """Estado resumido del cobro mensual del alumno."""

    UP_TO_DATE = "up_to_date"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"


class StudentStatus(str, Enum):
    """Estado operativo del alumno."""

    ACTIVE = "active"
    FROZEN = "frozen"
    INACTIVE = "inactive"


class AttendanceMethod(str, Enum):
    """Método con el que se registró la asistencia."""

    QR = "qr"
    MANUAL = "manual"


def db_enum(enum_class: type[Enum], *, name: str) -> SqlEnum:
    """Configura SQLAlchemy para persistir los valores reales del enum."""

    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )
