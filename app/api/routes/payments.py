"""Endpoints CRUD para pagos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_active_user
from app.core.authorization import ensure_can_access_operational_scope, scope_branch_filter
from app.db.session import get_db
from app.models.enums import PaymentMethod, PaymentRecordStatus, PaymentStatus, UserRole
from app.models.finance import Payment
from app.models.organization import Branch, Organization
from app.models.student import Student
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.payment import PaymentCreate, PaymentRead, PaymentUpdate


router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_or_404(db: Session, payment_id: int) -> Payment:
    """Obtiene un pago existente o corta con 404."""

    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pago no encontrado")
    return payment


def validate_payment_update_nulls(changes: dict[str, object]) -> None:
    """Evita que campos obligatorios reciban `null` en un PATCH."""

    required_fields = {
        "student_id",
        "organization_id",
        "branch_id",
        "amount",
        "currency",
        "period_start",
        "period_end",
        "paid_at",
        "method",
        "status",
        "recorded_by",
    }
    for field_name in required_fields:
        if field_name in changes and changes[field_name] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} no puede ser null",
            )


def validate_payment_links(
    db: Session,
    *,
    student_id: int,
    organization_id: int,
    branch_id: int,
    recorded_by: int,
) -> None:
    """Valida coherencia entre alumno, organización, sucursal y usuario registrador."""

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")
    if student.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pueden registrar pagos para un alumno eliminado lógicamente",
        )

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

    if student.organization_id != organization_id or student.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El alumno debe pertenecer a la misma organización y sucursal del pago",
        )

    user = db.get(User, recorded_by)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario registrador no encontrado")
    if user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="recorded_by no puede apuntar a un usuario con rol student",
        )


def sync_student_financial_status(
    db: Session,
    *,
    student_id: int,
    payment_status: PaymentRecordStatus,
    period_end,
) -> None:
    """Sincroniza el resumen financiero del alumno segun la regla operativa acordada."""

    if payment_status != PaymentRecordStatus.PAID:
        return

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alumno no encontrado")

    student.payment_status = PaymentStatus.UP_TO_DATE
    student.next_payment_date = period_end


@router.post("", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Payment:
    """Crea un pago para un alumno."""

    validate_payment_links(
        db,
        student_id=payload.student_id,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
        recorded_by=payload.recorded_by,
    )

    ensure_can_access_operational_scope(
        current_user,
        organization_id=payload.organization_id,
        branch_id=payload.branch_id,
    )

    payment = Payment(**payload.model_dump())
    db.add(payment)
    sync_student_financial_status(
        db,
        student_id=payload.student_id,
        payment_status=payload.status,
        period_end=payload.period_end,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el pago por un conflicto de integridad",
        ) from exc

    db.refresh(payment)
    return payment


@router.get("", response_model=list[PaymentRead])
def list_payments(
    student_id: int | None = Query(default=None, gt=0),
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    recorded_by: int | None = Query(default=None, gt=0),
    method: PaymentMethod | None = None,
    status_filter: PaymentRecordStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> list[Payment]:
    """Lista pagos con filtros básicos."""

    organization_id, branch_id = scope_branch_filter(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )
    query = select(Payment).order_by(Payment.paid_at.desc(), Payment.id.desc())

    if student_id is not None:
        query = query.where(Payment.student_id == student_id)
    if organization_id is not None:
        query = query.where(Payment.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(Payment.branch_id == branch_id)
    if recorded_by is not None:
        query = query.where(Payment.recorded_by == recorded_by)
    if method is not None:
        query = query.where(Payment.method == method)
    if status_filter is not None:
        query = query.where(Payment.status == status_filter)

    return list(db.scalars(query).all())


@router.get("/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Payment:
    """Devuelve un pago por su id."""

    payment = get_payment_or_404(db, payment_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=payment.organization_id,
        branch_id=payment.branch_id,
    )
    return payment


@router.patch("/{payment_id}", response_model=PaymentRead)
def update_payment(
    payment_id: int,
    payload: PaymentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> Payment:
    """Actualiza de forma parcial un pago existente."""

    payment = get_payment_or_404(db, payment_id)
    changes = payload.model_dump(exclude_unset=True)
    validate_payment_update_nulls(changes)

    student_id = changes.get("student_id", payment.student_id)
    organization_id = changes.get("organization_id", payment.organization_id)
    branch_id = changes.get("branch_id", payment.branch_id)
    recorded_by = changes.get("recorded_by", payment.recorded_by)
    period_start = changes.get("period_start", payment.period_start)
    period_end = changes.get("period_end", payment.period_end)

    ensure_can_access_operational_scope(
        current_user,
        organization_id=organization_id,
        branch_id=branch_id,
    )

    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_start no puede ser mayor que period_end",
        )

    validate_payment_links(
        db,
        student_id=student_id,
        organization_id=organization_id,
        branch_id=branch_id,
        recorded_by=recorded_by,
    )

    for field_name, value in changes.items():
        setattr(payment, field_name, value)

    sync_student_financial_status(
        db,
        student_id=student_id,
        payment_status=payment.status,
        period_end=period_end,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el pago por un conflicto de integridad",
        ) from exc

    db.refresh(payment)
    return payment


@router.delete("/{payment_id}", response_model=MessageResponse)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
) -> MessageResponse:
    """Anula un pago sin borrar el historial financiero."""

    payment = get_payment_or_404(db, payment_id)
    ensure_can_access_operational_scope(
        current_user,
        organization_id=payment.organization_id,
        branch_id=payment.branch_id,
    )
    payment.status = PaymentRecordStatus.VOID
    db.commit()
    return MessageResponse(message="Pago anulado correctamente")
