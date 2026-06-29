"""Generación de códigos únicos para alumnos."""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.student import Student


ALPHANUMERIC = string.ascii_uppercase + string.digits


def build_student_unique_code(db: Session, organization: Organization) -> str:
    """Genera un código único con prefijo de organización.

    Formato: `ABC-1Z9X`
    """

    prefix = organization.slug.upper()

    for _ in range(20):
        suffix = "".join(secrets.choice(ALPHANUMERIC) for _ in range(4))
        candidate = f"{prefix}-{suffix}"
        exists = db.scalar(select(Student.id).where(Student.unique_code == candidate))
        if exists is None:
            return candidate

    raise RuntimeError("No fue posible generar un unique_code disponible")
