"""Endpoints públicos para captura web de asistencias."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from hmac import compare_digest
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import AttendanceMethod, StudentStatus
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.teaching import Attendance, MartialClass
from app.schemas.public_attendance import (
    PublicAttendanceContext,
    PublicAttendanceCreate,
    PublicAttendanceResult,
)


router = APIRouter(prefix="/public/attendance", tags=["public-attendance"])


def slugify_text(value: str) -> str:
    """Normaliza un texto para compararlo contra segmentos de URL."""

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    collapsed = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return collapsed


def resolve_public_scope(db: Session, organization_slug: str, branch_slug: str) -> tuple[Organization, Branch]:
    """Resuelve organización y sucursal usando slugs públicos."""

    organization = db.scalar(
        select(Organization).where(
            Organization.slug == organization_slug.strip().upper(),
            Organization.is_active.is_(True),
        )
    )
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado")

    branches = list(
        db.scalars(
            select(Branch).where(
                Branch.organization_id == organization.id,
                Branch.is_active.is_(True),
            )
        ).all()
    )
    branch = next((item for item in branches if slugify_text(item.name) == branch_slug), None)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")

    return organization, branch


def extract_qr_secret(raw_value: str) -> str:
    """Extrae el token útil desde un QR plano o una URL."""

    candidate = raw_value.strip()
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        for key in ("token", "qr", "secret"):
            values = query.get(key)
            if values and values[0].strip():
                return values[0].strip()
        tail = parsed.path.rstrip("/").split("/")[-1]
        if tail:
            return tail.strip()

    if ":" in candidate:
        prefix, value = candidate.split(":", 1)
        if prefix.lower() in {"qr", "token", "secret"} and value.strip():
            return value.strip()

    return candidate


def resolve_student_for_public_check_in(db: Session, branch: Branch, student_code: str) -> Student:
    """Busca un alumno activo de la sucursal por código público o id."""

    normalized_code = student_code.strip().upper()
    student = db.scalar(
        select(Student).where(
            Student.branch_id == branch.id,
            Student.deleted_at.is_(None),
            Student.unique_code == normalized_code,
        )
    )

    if student is None and normalized_code.isdigit():
        student = db.scalar(
            select(Student).where(
                Student.id == int(normalized_code),
                Student.branch_id == branch.id,
                Student.deleted_at.is_(None),
            )
        )

    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado en esta sucursal")
    if student.status != StudentStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El alumno no está activo")
    return student


@router.get("/{organization_slug}/{branch_slug}", response_model=PublicAttendanceContext)
def get_public_attendance_context(
    organization_slug: str,
    branch_slug: str,
    db: Session = Depends(get_db),
) -> PublicAttendanceContext:
    """Devuelve el contexto necesario para mostrar la pantalla pública."""

    organization, branch = resolve_public_scope(db, organization_slug, branch_slug)
    classes = list(
        db.scalars(
            select(MartialClass)
            .where(
                MartialClass.organization_id == organization.id,
                MartialClass.branch_id == branch.id,
                MartialClass.is_active.is_(True),
            )
            .order_by(MartialClass.name.asc(), MartialClass.id.asc())
        ).all()
    )

    return PublicAttendanceContext(
        organization_name=organization.name,
        organization_slug=organization.slug,
        branch_name=branch.name,
        branch_slug=slugify_text(branch.name),
        branch_id=branch.id,
        classes=classes,
    )


@router.post("/{organization_slug}/{branch_slug}", response_model=PublicAttendanceResult, status_code=status.HTTP_201_CREATED)
def create_public_attendance(
    organization_slug: str,
    branch_slug: str,
    payload: PublicAttendanceCreate,
    db: Session = Depends(get_db),
) -> PublicAttendanceResult:
    """Registra una asistencia desde una interfaz pública validada con QR."""

    organization, branch = resolve_public_scope(db, organization_slug, branch_slug)
    student = resolve_student_for_public_check_in(db, branch, payload.student_code)

    if student.organization_id != organization.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El alumno no pertenece al equipo")

    qr_secret = extract_qr_secret(payload.qr_token)
    if not qr_secret or not compare_digest(qr_secret, branch.qr_secret):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El QR escaneado no corresponde a esta sucursal")

    class_obj: MartialClass | None = None
    if payload.class_id is not None:
        class_obj = db.get(MartialClass, payload.class_id)
        if class_obj is None or not class_obj.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
        if class_obj.organization_id != organization.id or class_obj.branch_id != branch.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clase no pertenece a la sucursal seleccionada",
            )

    attendance = Attendance(
        student_id=student.id,
        class_id=payload.class_id,
        branch_id=branch.id,
        check_in_at=datetime.now(timezone.utc).replace(tzinfo=None),
        method=AttendanceMethod.QR,
        registered_by=None,
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    student_name = f"{student.first_name} {student.last_name}".strip()
    return PublicAttendanceResult(
        message="Tu asistencia ha sido registrada.",
        attendance_id=attendance.id,
        student_id=student.id,
        student_name=student_name,
        class_id=class_obj.id if class_obj is not None else None,
        class_name=class_obj.name if class_obj is not None else None,
        check_in_at=attendance.check_in_at,
    )
