"""Endpoints CRUD para usuarios y su alcance administrativo inicial."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.organization import Branch, Organization
from app.models.user import AdminAssignment, User
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate


router = APIRouter(prefix="/users", tags=["users"])


SCOPED_ADMIN_ROLES = {UserRole.ORG_ADMIN, UserRole.BRANCH_ADMIN}


def get_user_or_404(db: Session, user_id: int) -> User:
    """Obtiene un usuario con sus asignaciones o corta con 404."""

    query = (
        select(User)
        .options(selectinload(User.admin_assignments))
        .where(User.id == user_id)
    )
    user = db.scalar(query)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return user


def ensure_valid_scope(
    db: Session,
    role: UserRole,
    organization_id: int | None,
    branch_id: int | None,
) -> tuple[Organization | None, Branch | None]:
    """Valida que el alcance enviado sea coherente con el rol."""

    if role in {UserRole.SUPER_ADMIN, UserRole.STUDENT}:
        if organization_id is not None or branch_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ese rol no debe recibir organization_id ni branch_id",
            )
        return None, None

    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="organization_id es obligatorio para roles administrativos",
        )

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organización no encontrada")

    if role == UserRole.ORG_ADMIN:
        if branch_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ORG_ADMIN debe administrarse a nivel organización y no por sucursal",
            )
        return organization, None

    if branch_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="branch_id es obligatorio para BRANCH_ADMIN",
        )

    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")
    if branch.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La sucursal no pertenece a la organización indicada",
        )
    return organization, branch


def sync_admin_scope(
    user: User,
    role: UserRole,
    organization_id: int | None,
    branch_id: int | None,
) -> None:
    """Mantiene una sola asignación administrativa principal por usuario.

    Para esta primera versión del backend se expone un alcance único por usuario.
    Si en el futuro se requiere multi-asignación, este comportamiento se extiende
    sin romper la API pública actual.
    """

    if role not in SCOPED_ADMIN_ROLES:
        user.admin_assignments.clear()
        return

    if user.admin_assignments:
        assignment = user.admin_assignments[0]
        assignment.organization_id = organization_id  # type: ignore[assignment]
        assignment.branch_id = branch_id
        del user.admin_assignments[1:]
        return

    user.admin_assignments.append(
        AdminAssignment(
            organization_id=organization_id,  # type: ignore[arg-type]
            branch_id=branch_id,
        )
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Crea un usuario y, si aplica, su alcance administrativo inicial."""

    ensure_valid_scope(db, payload.role, payload.organization_id, payload.branch_id)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    sync_admin_scope(user, payload.role, payload.organization_id, payload.branch_id)
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear el usuario por un conflicto de integridad",
        ) from exc

    return get_user_or_404(db, user.id)


@router.get("", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    is_active: bool | None = None,
    organization_id: int | None = Query(default=None, gt=0),
    branch_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> list[User]:
    """Lista usuarios con filtros básicos por rol, estado y alcance."""

    query = select(User).options(selectinload(User.admin_assignments)).order_by(User.id)

    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if organization_id is not None or branch_id is not None:
        query = query.join(User.admin_assignments)
    if organization_id is not None:
        query = query.where(AdminAssignment.organization_id == organization_id)
    if branch_id is not None:
        query = query.where(AdminAssignment.branch_id == branch_id)

    return list(db.scalars(query.distinct()).all())


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    """Devuelve un usuario por su id."""

    return get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
) -> User:
    """Actualiza de forma parcial un usuario y su alcance principal."""

    user = get_user_or_404(db, user_id)
    changes = payload.model_dump(exclude_unset=True)

    target_role = changes.get("role", user.role)
    current_scope = user.admin_assignments[0] if user.admin_assignments else None

    if target_role in SCOPED_ADMIN_ROLES:
        organization_id = changes.get(
            "organization_id",
            current_scope.organization_id if current_scope else None,
        )
        branch_id = changes.get(
            "branch_id",
            current_scope.branch_id if current_scope else None,
        )
    else:
        organization_id = changes.get("organization_id")
        branch_id = changes.get("branch_id")

    ensure_valid_scope(db, target_role, organization_id, branch_id)

    if "email" in changes:
        user.email = changes["email"]
    if "password" in changes:
        user.password_hash = hash_password(changes["password"])
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    user.role = target_role

    sync_admin_scope(user, target_role, organization_id, branch_id)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible actualizar el usuario por un conflicto de integridad",
        ) from exc

    return get_user_or_404(db, user.id)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Realiza borrado lógico desactivando el usuario."""

    user = get_user_or_404(db, user_id)
    user.is_active = False
    db.commit()
    return MessageResponse(message="Usuario desactivado correctamente")
