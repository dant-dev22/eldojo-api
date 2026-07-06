"""Endpoints del perfil del alumno para la app móvil."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.student import Student
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.me import AvailableClassRead, MyProfileRead


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
