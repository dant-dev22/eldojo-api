"""Endpoints CRUD para alumnos."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
from app.core.student_codes import build_student_unique_code
from app.db.session import get_db
from app.models.belts import BeltLevel, BeltStripe
from app.models.enums import StudentStatus, UserRole
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.student import (
    StudentCreate,
    StudentProfileCompleteness,
    StudentRead,
    StudentUpdate,
)


router = APIRouter(prefix="/students", tags=["students"])


def _student_load_options(*, include_details: bool = False):
    opts = [
        selectinload(Student.current_belt_level),
        selectinload(Student.current_stripe),
    ]
    if include_details:
        opts += [
            selectinload(Student.emergency_contacts),
            selectinload(Student.medical_record),
            selectinload(Student.documents),
            selectinload(Student.authorized_persons),
        ]
    return tuple(opts)


def compute_profile_completeness(student: Student) -> StudentProfileCompleteness:
    """Calcula el porcentaje/campos faltantes de la ficha de alumno."""
    has_phone = bool(student.phone and student.phone.strip())
    has_email = bool(student.email and student.email.strip())
    has_emergency_contacts = bool(getattr(student, "emergency_contacts", None) and len(student.emergency_contacts) > 0)
    mr = getattr(student, "medical_record", None)
    has_medical_record = mr is not None and (
        bool(mr.blood_type)
        or bool(mr.allergies)
        or bool(mr.previous_injuries)
        or mr.insurance_type != "none"
    )
    docs = getattr(student, "documents", []) or []
    has_liability_waiver = any(d.document_type == "liability_waiver" for d in docs)
    has_photo_consent = any(d.document_type == "photo_consent" for d in docs)
    aps = getattr(student, "authorized_persons", None) or []
    is_minor = student.is_minor or False
    has_authorized_persons_if_minor = (not is_minor) or (len([ap for ap in aps if ap.is_active]) > 0)

    checks = [
        ("phone", has_phone),
        ("email", has_email),
        ("emergency_contacts", has_emergency_contacts),
        ("medical_record", has_medical_record),
        ("liability_waiver", has_liability_waiver),
        ("photo_consent", has_photo_consent),
    ]
    if is_minor:
        checks.append(("authorized_persons", has_authorized_persons_if_minor))

    missing_fields = [name for name, ok in checks if not ok]
    filled_fields = len(checks) - len(missing_fields)
    return StudentProfileCompleteness(
        is_complete=len(missing_fields) == 0,
        total_fields=len(checks),
        filled_fields=filled_fields,
        missing_fields=missing_fields,
        has_phone=has_phone,
        has_email=has_email,
        has_emergency_contacts=has_emergency_contacts,
        has_medical_record=has_medical_record,
        has_liability_waiver=has_liability_waiver,
        has_photo_consent=has_photo_consent,
        has_authorized_persons_if_minor=has_authorized_persons_if_minor,
    )


def attach_completeness(student: Student) -> Student:
    """Adjunta el atributo dinámico profile_completeness al modelo ORM."""
    object.__setattr__(student, "profile_completeness", compute_profile_completeness(student))
    return student


def get_student_or_404(db: Session, student_id: int, *, include_details: bool = False) -> Student:
    """Obtiene un alumno existente o corta con 404."""

    student = db.scalar(
        select(Student)
        .where(Student.id == student_id)
        .options(*_student_load_options(include_details=include_details))
    )
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    return student


def validate_belt_links(
    db: Session,
    *,
    organization_id: int,
    current_belt_level_id: int | None,
    current_stripe_id: int | None,
) -> None:
    """Valida que el nivel de cinta y stripe pertenezcan a la organización y sean coherentes."""

    if current_belt_level_id is None and current_stripe_id is None:
        return

    belt_level: BeltLevel | None = None
    if current_belt_level_id is not None:
        belt_level = db.get(BeltLevel, current_belt_level_id)
        if belt_level is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nivel de cinta no encontrado",
            )
        if belt_level.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El nivel de cinta no pertenece a la organización indicada",
            )

    if current_stripe_id is not None:
        stripe = db.get(BeltStripe, current_stripe_id)
        if stripe is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stripe de cinta no encontrado",
            )
        stripe_level = db.get(BeltLevel, stripe.belt_level_id)
        if stripe_level is None or stripe_level.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El stripe de cinta no pertenece a la organización indicada",
            )
        if current_belt_level_id is not None and stripe.belt_level_id != current_belt_level_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El stripe seleccionado no pertenece al nivel de cinta indicado",
            )


def validate_student_links(
    db: Session,
    *,
    organization_id: int,
    branch_id: int,
    user_id: int | None,
    primary_class_id: int | None,
    current_belt_level_id: int | None = None,
    current_stripe_id: int | None = None,
) -> Organization:
    """Valida referencias y coherencia entre organización, sucursal, clase y cinturones."""

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organización no encontrada")

    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")
    if branch.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La sucursal no pertenece a la organización indicada",
        )

    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        if user.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Solo se puede vincular un usuario con rol student",
            )

    if primary_class_id is not None:
        martial_class = db.get(MartialClass, primary_class_id)
        if martial_class is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clase no encontrada")
        if martial_class.organization_id != organization_id or martial_class.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La clase principal debe pertenecer a la misma organización y sucursal del alumno",
            )

    validate_belt_links(
        db,
        organization_id=organization_id,
        current_belt_level_id=current_belt_level_id,
        current_stripe_id=current_stripe_id,
    )

    return organization


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Crea un alumno y genera su `unique_code` automáticamente."""

    ensure_can_access_operational_scope(
        current_user,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
    )
    organization = validate_student_links(
        db,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        user_id=payload.user_id,
        primary_class_id=payload.primary_class_id,
        current_belt_level_id=payload.current_belt_level_id,
        current_stripe_id=payload.current_stripe_id,
    )

    student = Student(
        **payload.model_dump(),
        unique_code=build_student_unique_code(db, organization),
    )
    db.add(student)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el alumno por un conflicto de integridad",
        ) from exc

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options(include_details=True))
    )
    result = refreshed or student
    return attach_completeness(result)


@router.get("", response_model=list[StudentRead])
def list_students(
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    incomplete_only: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    include_deleted: bool = False,
    include_completeness: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Student]:
    """Lista alumnos con filtros por organización, sucursal, estado y nombre."""

    organization_id, branch_id = scope_branch_filter(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )
    load_details = include_completeness or incomplete_only
    query = (
        select(Student)
        .options(*_student_load_options(include_details=load_details))
        .order_by(Student.id)
    )

    if organization_id is not None:
        query = query.where(Student.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(Student.branch_id == branch_id)
    if status_filter is not None:
        query = query.where(Student.status == status_filter)
    if search is not None:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Student.first_name.like(search_term),
                Student.last_name.like(search_term),
            )
        )
    if not include_deleted:
        query = query.where(Student.deleted_at.is_(None))

    students = list(db.scalars(query).unique().all())
    if include_completeness or incomplete_only:
        processed: list[Student] = []
        for s in students:
            attach_completeness(s)
            if incomplete_only and s.profile_completeness and s.profile_completeness.is_complete:
                continue
            processed.append(s)
        return processed
    return students


@router.get("/{student_id}", response_model=StudentRead)
def get_student(
    student_id: int,
    include_deleted: bool = False,
    include_details: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Devuelve un alumno por su id, opcionalmente con detalle médico/documentos."""

    student = get_student_or_404(db, student_id, include_details=include_details)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    if student.deleted_at is not None and not include_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    if include_details:
        attach_completeness(student)
    return student


@router.get("/{student_id}/profile-completeness", response_model=StudentProfileCompleteness)
def get_student_profile_completeness(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentProfileCompleteness:
    """Devuelve el diagnóstico de completitud de la ficha del alumno."""

    student = get_student_or_404(db, student_id, include_details=True)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    return compute_profile_completeness(student)


@router.patch("/{student_id}", response_model=StudentRead)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Actualiza de forma parcial un alumno existente."""

    student = get_student_or_404(db, student_id)
    changes = payload.model_dump(exclude_unset=True)

    organization_id = changes.get("organization_id", student.organization_id)
    branch_id = changes.get("branch_id", student.branch_id)
    user_id = changes.get("user_id", student.user_id)
    primary_class_id = changes.get("primary_class_id", student.primary_class_id)
    current_belt_level_id = changes.get("current_belt_level_id", student.current_belt_level_id)
    current_stripe_id = changes.get("current_stripe_id", student.current_stripe_id)

    ensure_can_access_operational_scope(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )

    validate_student_links(
        db,
        organization_id=organization_id,
        branch_id=branch_id,
        user_id=user_id,
        primary_class_id=primary_class_id,
        current_belt_level_id=current_belt_level_id,
        current_stripe_id=current_stripe_id,
    )

    for field_name, value in changes.items():
        setattr(student, field_name, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el alumno por un conflicto de integridad",
        ) from exc

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options(include_details=True))
    )
    result = refreshed or student
    return attach_completeness(result)


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Realiza el soft delete del alumno."""

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    student.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    student.status = StudentStatus.INACTIVE
    db.commit()
    return MessageResponse(message="Alumno eliminado lógicamente")


# ======================== Sub-recursos ========================
# Rutas anidadas: /students/{student_id}/emergency-contacts
#                /students/{student_id}/medical-record
#                /students/{student_id}/documents
#                /students/{student_id}/authorized-persons


@router.get("/{student_id}/emergency-contacts", response_model=list)
def list_student_emergency_contacts(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.emergency_contact import EmergencyContact
    from app.schemas.emergency_contact import EmergencyContactRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    items = db.scalars(
        select(EmergencyContact)
        .where(EmergencyContact.student_id == student_id, EmergencyContact.deleted_at.is_(None))
        .order_by(EmergencyContact.priority, EmergencyContact.id)
    ).all()
    return [EmergencyContactRead.model_validate(i) for i in items]


@router.post("/{student_id}/emergency-contacts", response_model=None, status_code=201)
def create_student_emergency_contact(
    student_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.emergency_contact import EmergencyContact
    from app.schemas.emergency_contact import EmergencyContactCreate, EmergencyContactRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    create = EmergencyContactCreate(student_id=student_id, organization_id=student.organization_id, **payload)
    obj = EmergencyContact(**create.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return EmergencyContactRead.model_validate(obj)


@router.get("/{student_id}/medical-record", response_model=None)
def get_student_medical_record(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.medical_record import MedicalRecord
    from app.schemas.medical_record import MedicalRecordRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    obj = db.scalar(
        select(MedicalRecord).where(MedicalRecord.student_id == student_id, MedicalRecord.deleted_at.is_(None))
    )
    return MedicalRecordRead.model_validate(obj) if obj else None


@router.put("/{student_id}/medical-record", response_model=None)
def upsert_student_medical_record(
    student_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.medical_record import MedicalRecord
    from app.schemas.medical_record import MedicalRecordCreate, MedicalRecordRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    existing = db.scalar(
        select(MedicalRecord).where(MedicalRecord.student_id == student_id, MedicalRecord.deleted_at.is_(None))
    )
    if existing is None:
        create = MedicalRecordCreate(student_id=student_id, organization_id=student.organization_id, **payload)
        obj = MedicalRecord(**create.model_dump())
        db.add(obj)
    else:
        for key, value in payload.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        obj = existing
    db.commit()
    db.refresh(obj)
    return MedicalRecordRead.model_validate(obj)


@router.get("/{student_id}/documents", response_model=list)
def list_student_documents(
    student_id: int,
    document_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.student_document import StudentDocument
    from app.schemas.student_document import StudentDocumentRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    query = select(StudentDocument).where(StudentDocument.student_id == student_id, StudentDocument.deleted_at.is_(None))
    if document_type:
        query = query.where(StudentDocument.document_type == document_type)
    items = db.scalars(query.order_by(StudentDocument.created_at.desc())).all()
    return [StudentDocumentRead.model_validate(i) for i in items]


@router.post("/{student_id}/documents", response_model=None, status_code=201)
def create_student_document(
    student_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.student_document import StudentDocument
    from app.schemas.student_document import StudentDocumentCreate, StudentDocumentRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    create = StudentDocumentCreate(student_id=student_id, organization_id=student.organization_id, **payload)
    obj = StudentDocument(**create.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return StudentDocumentRead.model_validate(obj)


@router.get("/{student_id}/authorized-persons", response_model=list)
def list_student_authorized_persons(
    student_id: int,
    only_active: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.authorized_person import AuthorizedPerson
    from app.schemas.authorized_person import AuthorizedPersonRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    query = select(AuthorizedPerson).where(AuthorizedPerson.student_id == student_id, AuthorizedPerson.deleted_at.is_(None))
    if only_active:
        query = query.where(AuthorizedPerson.is_active == True)
    items = db.scalars(query.order_by(AuthorizedPerson.full_name)).all()
    return [AuthorizedPersonRead.model_validate(i) for i in items]


@router.post("/{student_id}/authorized-persons", response_model=None, status_code=201)
def create_student_authorized_person(
    student_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    from app.models.authorized_person import AuthorizedPerson
    from app.schemas.authorized_person import AuthorizedPersonCreate, AuthorizedPersonRead

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(current_user, organization_id=student.organization_id, branch_id=student.branch_id)
    create = AuthorizedPersonCreate(student_id=student_id, organization_id=student.organization_id, **payload)
    obj = AuthorizedPerson(**create.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return AuthorizedPersonRead.model_validate(obj)
