"""Endpoints CRUD para alumnos."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
from app.core.security import hash_password
from app.core.student_codes import build_student_unique_code
from app.core.student_invitation import (
    build_student_invitation_link,
    generate_student_invitation_token,
    invalidate_student_invitations,
    student_invitation_expires_at,
)
from app.db.session import get_db
from app.models.belts import BeltLevel, BeltStripe
from app.models.enums import StudentStatus, UserRole
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.student_invitation import StudentInvitationToken
from app.models.teaching import MartialClass
from app.models.user import User
from app.schemas.attendance import StudentAttendanceSummary
from app.schemas.common import MessageResponse
from app.schemas.student import (
    StudentCreate,
    StudentPortalAccessStatus,
    StudentProfileCompleteness,
    StudentRead,
    StudentUpdate,
)
from app.services.attendance_summary_service import build_student_attendance_summary


def _utc_now() -> datetime:
    """Helper para UTC naive coherente con la base actual."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


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

    value = compute_profile_completeness(student)
    object.__setattr__(student, "profile_completeness", value)
    try:
        student.__dict__["profile_completeness"] = value
    except Exception:
        pass
    return student


def _populate_portal_access_status(
    db: Session,
    student: Student,
    *,
    latest_raw_token: str | None = None,
) -> StudentPortalAccessStatus:
    """Construye el estado de acceso al portal para un alumno.

    Si `latest_raw_token` se provee (solo se dispone de él inmediatamente
    después de generar una invitación nueva), se incluye `invitation_link`
    con la URL pública. En cualquier otro caso, el valor raw no está
    accesible desde la BD (solo se guarda el hash) y el link se omite.
    """

    status_obj = StudentPortalAccessStatus()

    if student.user_id is not None:
        user = db.get(User, student.user_id)
        if user is not None:
            status_obj.has_linked_user = True
            status_obj.user_is_active = bool(user.is_active)
            status_obj.user_email_verified = user.email_verified_at is not None

    latest_invitation = db.scalar(
        select(StudentInvitationToken)
        .where(StudentInvitationToken.student_id == student.id)
        .order_by(StudentInvitationToken.created_at.desc(), StudentInvitationToken.id.desc())
    )
    if latest_invitation is not None:
        is_not_expired = (
            latest_invitation.expires_at is None
            or latest_invitation.expires_at > _utc_now()
        )
        is_pending = latest_invitation.used_at is None and is_not_expired
        status_obj.pending_invitation_exists = is_pending
        if is_pending:
            status_obj.invitation_expires_at = latest_invitation.expires_at
        status_obj.invitation_sent_count = int(latest_invitation.sent_count or 0)
        status_obj.invitation_email_sent_to = latest_invitation.email_sent_to

    if latest_raw_token:
        status_obj.invitation_link = build_student_invitation_link(latest_raw_token)

    return status_obj


def attach_portal_access(db: Session, student: Student, *, latest_raw_token: str | None = None) -> Student:
    """Adjunta el estado portal_access al ORM Student como atributo dinámico."""

    value = _populate_portal_access_status(db, student, latest_raw_token=latest_raw_token)
    object.__setattr__(student, "portal_access", value)
    try:
        student.__dict__["portal_access"] = value
    except Exception:
        pass
    return student


def _ensure_student_has_portal_user(
    db: Session,
    student: Student,
    *,
    unique_code: str | None = None,
    student_email: str | None = None,
) -> User:
    """Asegura que el alumno tenga un User de portal STUDENT vinculado.

    Si `student.user_id` ya existe, devuelve ese User (incluso si está
    inactivo: el caller lo activa si corresponde).
    Si no existe, crea un User placeholder bloqueado (igual que el flujo
    create_student) y vincula `student.user_id`. Usa el `unique_code`
    provisto o vuelve a leer `student.unique_code` para armar el email
    placeholder `{code}@pendiente.eldojo.tech`.
    """

    if student.user_id is not None:
        existing = db.get(User, student.user_id)
        if existing is not None:
            return existing

    code = (unique_code or student.unique_code or "").strip() or f"s{student.id}"
    placeholder_email = f"{code.lower()}@pendiente.eldojo.tech"
    temp_password = secrets.token_urlsafe(16)
    portal_user = User(
        first_name=student.first_name,
        last_name=student.last_name,
        email=placeholder_email,
        password_hash=hash_password(temp_password),
        role=UserRole.STUDENT,
        is_active=True,
        email_verified_at=None,
        first_time=True,
        last_login_at=None,
    )
    db.add(portal_user)
    db.flush()
    student.user_id = portal_user.id
    if student_email:
        object.__setattr__(portal_user, "_pending_invitation_email", student_email)
    return portal_user


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
    """Crea un alumno y genera su `unique_code` automáticamente.

    Si `enable_portal_access=True` y no se proporcionó `user_id`:
      - Crea un User STUDENT placeholder con credenciales temporales bloqueadas
        para login normal (email_verified_at=None).
      - Genera y persiste un token de invitación.
      - Devuelve `portal_access.invitation_link` con el enlace público que
        el admin debe compartir con el alumno.
    """

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

    unique_code = build_student_unique_code(db, organization)
    should_enable_portal = bool(payload.enable_portal_access) and payload.user_id is None

    student_data = payload.model_dump(exclude={"enable_portal_access", "student_email"})
    student = Student(**student_data, unique_code=unique_code)
    db.add(student)

    generated_raw_token: str | None = None

    try:
        db.flush()

        if should_enable_portal:
            portal_user = _ensure_student_has_portal_user(
                db,
                student,
                unique_code=unique_code,
                student_email=payload.student_email,
            )
            raw_token, token_hash, token_tail = generate_student_invitation_token()
            db.add(
                StudentInvitationToken(
                    student_id=student.id,
                    user_id=portal_user.id,
                    token_hash=token_hash,
                    token_plain_tail=token_tail,
                    expires_at=student_invitation_expires_at(),
                    used_at=None,
                    sent_count=1,
                    created_by_admin_id=current_user.id,
                    email_sent_to=payload.student_email,
                )
            )
            generated_raw_token = raw_token

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
    attach_completeness(result)
    attach_portal_access(db, result, latest_raw_token=generated_raw_token)
    return result


def build_student_read(student: Student) -> StudentRead:
    """Construye un StudentRead incluyendo atributos dinámicos.

    Pydantic v2 con from_attributes=True no siempre captura attrs dinámicos
    agregados por setattr (ej: portal_access, profile_completeness). Para
    garantizar la serialización, armamos un dict fuente combinando el
    __dict__ del ORM (con Columns) más los atributos dinámicos explícitos,
    y construimos el modelo Pydantic desde ese dict (no from_attributes).
    """

    base: dict[str, object] = {}
    try:
        # Claves de Column y relationships cargadas por SQLAlchemy.
        base.update({k: v for k, v in student.__dict__.items() if not k.startswith("_sa_")})
    except Exception:
        pass

    # Sobreescribir/agregar attrs dinámicos si existen.
    portal_access = getattr(student, "portal_access", None)
    profile_completeness = getattr(student, "profile_completeness", None)
    if portal_access is not None:
        base["portal_access"] = portal_access
    if profile_completeness is not None:
        base["profile_completeness"] = profile_completeness

    return StudentRead.model_validate(base)


@router.get("", response_model=list[StudentRead])
def list_students(
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    incomplete_only: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    include_deleted: bool = False,
    include_completeness: bool = Query(default=True),
    include_portal_access: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Student]:
    """Lista alumnos con filtros por organización, sucursal, estado y nombre.

    `include_portal_access` es opt-in (default=False) por performance:
    requiere hasta 2 queries adicionales por alumno (User + último token).
    """

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
                Student.unique_code.like(search_term),
            )
        )
    if not include_deleted:
        query = query.where(Student.deleted_at.is_(None))

    students = list(db.scalars(query).unique().all())
    processed: list[Student] = []
    for s in students:
        skip = False
        if include_completeness or incomplete_only:
            attach_completeness(s)
            if incomplete_only and s.profile_completeness and s.profile_completeness.is_complete:
                skip = True
        if not skip and include_portal_access:
            attach_portal_access(db, s)
        if not skip:
            processed.append(s)
    return [build_student_read(s) for s in processed]


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
    attach_portal_access(db, student)
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


@router.get("/{student_id}/attendance/summary", response_model=StudentAttendanceSummary)
def get_student_attendance_summary(
    student_id: int,
    class_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentAttendanceSummary:
    """KPIs y agregados de asistencia para un alumno específico."""

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    return build_student_attendance_summary(
        db,
        student,
        class_id=class_id,
        date_from=date_from,
        date_to=date_to,
    )


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


# ======================== Portal Access (admin) ========================


@router.get("/{student_id}/portal-access", response_model=StudentPortalAccessStatus)
def get_student_portal_access_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> StudentPortalAccessStatus:
    """Devuelve el estado del portal del alumno (sin exponer links)."""

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )
    return _populate_portal_access_status(db, student)


@router.post("/{student_id}/resend-invitation", response_model=StudentRead)
def resend_student_invitation(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Genera o regenera la invitación del portal manteniendo máximo 1 pendiente.

    - Si existe un token PENDIENTE (no usado y no vencido) para el alumno,
      se REUTILIZA ese mismo row actualizando hash/fecha/sent_count (no se
      insertan filas nuevas, no hay filas en la tabla por reenvío).
    - Si no hay token pendiente, se crea uno nuevo.
    - Si el alumno aún no tiene usuario portal o estaba inactivo, se crea o
      re-activa automáticamente.
    - El link generado (raw token) solo se devuelve en esta respuesta via
      `portal_access.invitation_link`.
    """

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    now = _utc_now()
    existing_pending = db.scalar(
        select(StudentInvitationToken)
        .where(StudentInvitationToken.student_id == student.id)
        .order_by(StudentInvitationToken.created_at.desc(), StudentInvitationToken.id.desc())
        .limit(1)
    )
    is_pending_existing = False
    if existing_pending is not None:
        is_not_expired = (
            existing_pending.expires_at is None
            or existing_pending.expires_at > now
        )
        is_pending_existing = existing_pending.used_at is None and is_not_expired

    last_email_sent_to = getattr(existing_pending, "email_sent_to", None)
    if is_pending_existing:
        new_sent_count = int(getattr(existing_pending, "sent_count", 0) or 0) + 1
    else:
        new_sent_count = int(getattr(existing_pending, "sent_count", 0) or 0) + 1

    portal_user = _ensure_student_has_portal_user(
        db,
        student,
        student_email=last_email_sent_to,
    )
    if not portal_user.is_active:
        portal_user.is_active = True

    raw_token, token_hash, token_tail = generate_student_invitation_token()

    if is_pending_existing and existing_pending is not None:
        existing_pending.token_hash = token_hash
        existing_pending.token_plain_tail = token_tail
        existing_pending.expires_at = student_invitation_expires_at()
        existing_pending.sent_count = new_sent_count
        existing_pending.created_by_admin_id = current_user.id
        existing_pending.created_at = now
        existing_pending.user_id = portal_user.id
    else:
        if existing_pending is not None:
            existing_pending.used_at = now
        db.add(
            StudentInvitationToken(
                student_id=student.id,
                user_id=portal_user.id,
                token_hash=token_hash,
                token_plain_tail=token_tail,
                expires_at=student_invitation_expires_at(),
                used_at=None,
                sent_count=new_sent_count,
                created_by_admin_id=current_user.id,
                email_sent_to=last_email_sent_to,
            )
        )

    db.commit()

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options(include_details=True))
    )
    result = refreshed or student
    attach_completeness(result)
    attach_portal_access(db, result, latest_raw_token=raw_token)
    return result


@router.post("/{student_id}/revoke-portal-access", response_model=StudentRead)
def revoke_student_portal_access(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Student:
    """Desactiva el usuario vinculado al alumno e invalida todas sus invitaciones.

    El alumno no podrá iniciar sesión ni canjear tokens después de esta acción.
    """

    student = get_student_or_404(db, student_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=student.organization_id,
        branch_id=student.branch_id,
    )

    if student.user_id is not None:
        user = db.get(User, student.user_id)
        if user is not None:
            user.is_active = False

    invalidate_student_invitations(db, student_id=student.id, used_at=_utc_now())
    db.commit()

    refreshed = db.scalar(
        select(Student)
        .where(Student.id == student.id)
        .options(*_student_load_options(include_details=True))
    )
    result = refreshed or student
    attach_completeness(result)
    attach_portal_access(db, result)
    return result


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
