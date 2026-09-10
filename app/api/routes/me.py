"""Endpoints del perfil del alumno para la app móvil."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user, require_student_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.student import Student
from app.models.teaching import Attendance, MartialClass
from app.models.user import User
from app.schemas.attendance import AttendanceRead, StudentAttendanceSummary
from app.schemas.common import MessageResponse
from app.schemas.me import (
    AvailableClassRead,
    MyEmailChangeRequest,
    MyPasswordChangeRequest,
    MyProfileRead,
)
from app.services.attendance_summary_service import build_student_attendance_summary


router = APIRouter(prefix="/me", tags=["me"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024


def get_current_student(db: Session, current_user: User) -> Student:
    """Obtiene el alumno vinculado al usuario autenticado."""

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint solo está disponible para alumnos",
        )

    student = db.scalar(
        select(Student)
        .where(Student.user_id == current_user.id)
        .where(Student.deleted_at.is_(None))
    )
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un perfil de alumno vinculado al usuario autenticado",
        )
    return student


def list_available_classes(db: Session, student: Student) -> list[MartialClass]:
    """Devuelve las clases activas que puede seleccionar el alumno."""

    return list(
        db.scalars(
            select(MartialClass)
            .where(MartialClass.organization_id == student.organization_id)
            .where(MartialClass.branch_id == student.branch_id)
            .where(MartialClass.is_active.is_(True))
            .order_by(MartialClass.name)
        ).all()
    )


def build_public_photo_url(request: Request, photo_url: str | None) -> str | None:
    """Convierte la ruta almacenada a una URL pública consumible desde mobile."""

    if photo_url is None:
        return None
    if photo_url.startswith("http://") or photo_url.startswith("https://"):
        return photo_url
    return f"{str(request.base_url).rstrip('/')}{photo_url}"


def serialize_profile(
    request: Request,
    *,
    current_user: User,
    student: Student,
    available_classes: list[MartialClass],
) -> MyProfileRead:
    """Arma la respuesta de perfil que necesita la app móvil."""

    return MyProfileRead(
        user_id=current_user.id,
        student_id=student.id,
        email=current_user.email,
        role=current_user.role,
        unique_code=student.unique_code,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=f"{student.first_name} {student.last_name}",
        birth_date=student.birth_date,
        photo_url=build_public_photo_url(request, student.photo_url),
        current_class_id=student.primary_class_id,
        payment_status=student.payment_status,
        next_payment_date=student.next_payment_date,
        status=student.status,
        available_classes=[
            AvailableClassRead(
                id=class_obj.id,
                name=class_obj.name,
                description=class_obj.description,
                instructor_name=class_obj.instructor_name,
                is_active=class_obj.is_active,
            )
            for class_obj in available_classes
        ],
    )


@router.get("", response_model=MyProfileRead)
def read_my_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MyProfileRead:
    """Devuelve el perfil móvil del alumno autenticado."""

    student = get_current_student(db, current_user)
    available_classes = list_available_classes(db, student)
    return serialize_profile(
        request,
        current_user=current_user,
        student=student,
        available_classes=available_classes,
    )


@router.patch("", response_model=MyProfileRead)
async def update_my_profile(
    request: Request,
    primary_class_id: int | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MyProfileRead:
    """Actualiza la clase principal y/o la foto del alumno autenticado."""

    student = get_current_student(db, current_user)

    if primary_class_id is not None:
        class_obj = db.get(MartialClass, primary_class_id)
        if class_obj is None or not class_obj.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
        if (
            class_obj.organization_id != student.organization_id
            or class_obj.branch_id != student.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clase seleccionada no pertenece a la misma sucursal del alumno",
            )
        student.primary_class_id = primary_class_id

    if photo is not None:
        extension = Path(photo.filename or "").suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Formato de imagen no soportado",
            )

        file_bytes = await photo.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La imagen enviada está vacía",
            )
        if len(file_bytes) > MAX_PHOTO_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="La imagen excede el tamaño máximo permitido",
            )

        uploads_dir = request.app.state.uploads_dir / "profile-photos"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"student-{student.id}-{uuid4().hex}{extension}"
        (uploads_dir / file_name).write_bytes(file_bytes)
        student.photo_url = f"{request.app.state.uploads_url_prefix}/profile-photos/{file_name}"

    db.commit()
    db.refresh(student)
    available_classes = list_available_classes(db, student)
    return serialize_profile(
        request,
        current_user=current_user,
        student=student,
        available_classes=available_classes,
    )


# ======================== Seguridad (alumno-only) ========================


@router.patch("/password", response_model=MessageResponse)
def change_my_password(
    payload: MyPasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student_user),
) -> MessageResponse:
    """Cambia la contraseña del alumno autenticado.

    Requiere la contraseña actual para evitar robo de sesión. Valida que
    la contraseña nueva sea distinta a la anterior y que coincida con
    su confirmación (reglas de Pydantic).
    """

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual no es correcta",
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Contraseña actualizada correctamente")


@router.patch("/email", response_model=MyProfileRead)
def change_my_email(
    request: Request,
    payload: MyEmailChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student_user),
) -> MyProfileRead:
    """Cambia el correo del alumno autenticado.

    Marca automáticamente el nuevo correo como verificado (el alumno
    ya está autenticado) y valida que el correo no exista en otra cuenta.
    Devuelve el perfil actualizado con el nuevo email.
    """

    duplicate = db.scalar(
        select(User).where(User.email == payload.new_email, User.id != current_user.id)
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese correo ya está registrado en otra cuenta",
        )

    current_user.email = payload.new_email
    current_user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(current_user)

    student = get_current_student(db, current_user)
    available_classes = list_available_classes(db, student)
    return serialize_profile(
        request,
        current_user=current_user,
        student=student,
        available_classes=available_classes,
    )


# ======================== Asistencia (alumno-only) ========================


@router.get("/attendance", response_model=list[AttendanceRead])
def list_my_attendance(
    class_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=12),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student_user),
) -> list[Attendance]:
    """Historial de asistencias del alumno autenticado.

    Hard constraint: `limit` nunca supera 12 registros por solicitud.
    El filtro por `student_id` se hardcodea al alumno autenticado
    (seguridad crítica, no se acepta student_id del cliente).
    """

    student = get_current_student(db, current_user)

    predicates = [Attendance.student_id == student.id]
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
        .options(selectinload(Attendance.class_obj))
        .where(and_(*predicates))
        .order_by(Attendance.check_in_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.get("/attendance/summary", response_model=StudentAttendanceSummary)
def get_my_attendance_summary(
    class_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student_user),
) -> StudentAttendanceSummary:
    """KPIs y agregados de asistencia para el alumno autenticado.

    Reutiliza la misma lógica que usa el admin en `/students/{id}/attendance/summary`
    pero acota automáticamente el ámbito al alumno del token.
    """

    student = get_current_student(db, current_user)
    return build_student_attendance_summary(
        db,
        student,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
    )
