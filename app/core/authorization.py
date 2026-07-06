"""Reglas de autorización por rol y alcance administrativo."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.enums import UserRole
from app.models.user import User


def get_admin_scope_ids(current_user: User) -> tuple[int | None, int | None]:
    """Obtiene el alcance administrativo principal del usuario autenticado."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return None, None

    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu rol no tiene permisos para acceder a este recurso",
        )

    if not current_user.admin_assignments:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario autenticado no tiene un alcance administrativo configurado",
        )

    scope = current_user.admin_assignments[0]
    return scope.organization_id, scope.branch_id


def ensure_can_create_organization(current_user: User) -> None:
    """Restringe la creación de organizaciones a super admins."""

    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un super_admin puede crear organizaciones",
        )


def ensure_can_delete_organization(current_user: User) -> None:
    """Restringe el borrado lógico de organizaciones a super admins."""

    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un super_admin puede desactivar organizaciones",
        )


def ensure_can_manage_organization(current_user: User, organization_id: int) -> None:
    """Permite administrar una organización al super admin o su org admin."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    scope_organization_id, _ = get_admin_scope_ids(current_user)
    if current_user.role == UserRole.ORG_ADMIN and scope_organization_id == organization_id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para administrar esa organización",
    )


def ensure_can_read_organization(current_user: User, organization_id: int) -> None:
    """Permite ver una organización si cae dentro del alcance del usuario."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    scope_organization_id, _ = get_admin_scope_ids(current_user)
    if scope_organization_id == organization_id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para consultar esa organización",
    )


def ensure_can_create_branch(current_user: User, organization_id: int) -> None:
    """Permite crear sucursales a super admin y org admin del tenant."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    scope_organization_id, _ = get_admin_scope_ids(current_user)
    if current_user.role == UserRole.ORG_ADMIN and scope_organization_id == organization_id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para crear sucursales en esa organización",
    )


def ensure_can_manage_branch(current_user: User, organization_id: int, branch_id: int) -> None:
    """Permite administrar una sucursal según el alcance del usuario."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    scope_organization_id, scope_branch_id = get_admin_scope_ids(current_user)
    if scope_organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para esa organización",
        )

    if current_user.role == UserRole.ORG_ADMIN:
        return

    if current_user.role == UserRole.BRANCH_ADMIN and scope_branch_id == branch_id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para administrar esa sucursal",
    )


def ensure_can_access_operational_scope(
    current_user: User,
    *,
    organization_id: int,
    branch_id: int,
) -> None:
    """Permite operar recursos acotados por organización y sucursal."""

    ensure_can_manage_branch(current_user, organization_id, branch_id)


def scope_organization_filter(
    current_user: User,
    organization_id: int | None,
    *,
    allow_branch_admin: bool = True,
) -> int | None:
    """Ajusta el filtro de organización al alcance del usuario autenticado."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return organization_id

    scope_organization_id, _ = get_admin_scope_ids(current_user)

    if current_user.role == UserRole.BRANCH_ADMIN and not allow_branch_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu rol no puede consultar este recurso a nivel organización",
        )

    if organization_id is not None and organization_id != scope_organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El filtro organization_id está fuera de tu alcance",
        )

    return scope_organization_id


def scope_branch_filter(
    current_user: User,
    *,
    organization_id: int | None,
    branch_id: int | None,
    allow_branch_admin: bool = True,
) -> tuple[int | None, int | None]:
    """Ajusta los filtros de organización y sucursal al alcance del usuario."""

    effective_organization_id = scope_organization_filter(
        current_user,
        organization_id,
        allow_branch_admin=allow_branch_admin,
    )

    if current_user.role == UserRole.SUPER_ADMIN:
        return effective_organization_id, branch_id

    _, scope_branch_id = get_admin_scope_ids(current_user)

    if current_user.role == UserRole.ORG_ADMIN:
        return effective_organization_id, branch_id

    if not allow_branch_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu rol no puede consultar este recurso por sucursal",
        )

    if branch_id is not None and branch_id != scope_branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El filtro branch_id está fuera de tu alcance",
        )

    return effective_organization_id, scope_branch_id


def ensure_can_access_users_endpoint(current_user: User) -> None:
    """Permite usar el endpoint de usuarios solo a super admins y org admins."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    if current_user.role == UserRole.ORG_ADMIN:
        get_admin_scope_ids(current_user)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Tu rol no tiene permisos para administrar usuarios",
    )


def ensure_can_manage_user_role(current_user: User, target_role: UserRole) -> None:
    """Restringe qué tipos de usuario puede crear o modificar cada rol."""

    if current_user.role == UserRole.SUPER_ADMIN:
        return

    ensure_can_access_users_endpoint(current_user)
    if target_role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un super_admin puede gestionar usuarios super_admin",
        )
