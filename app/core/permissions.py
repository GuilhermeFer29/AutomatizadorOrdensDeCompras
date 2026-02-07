"""
Role-Based Access Control (RBAC) - Sistema de Permissoes SaaS.

ROLES:
- owner: Dono do tenant (acesso total)
- admin: Administrador (gerencia usuarios e configuracoes)
- manager: Gerente (aprova ordens, gerencia produtos)
- operator: Operador (cria ordens, visualiza dados)
- viewer: Visualizador (apenas leitura)

Uso:
    from app.core.permissions import require_role, require_permission

    @router.post("/orders")
    async def create_order(
        user=Depends(require_role("operator", "manager", "admin", "owner"))
    ):
        ...

    @router.delete("/users/{id}")
    async def delete_user(
        user=Depends(require_permission("manage_users"))
    ):
        ...

Autor: Sistema PMI | Data: 2026-02-06
"""

from __future__ import annotations

import logging
from enum import Enum

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user

LOGGER = logging.getLogger(__name__)


# ============================================================================
# ROLES
# ============================================================================

class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Hierarquia de roles (maior indice = mais privilegios)
ROLE_HIERARCHY = {
    Role.VIEWER: 0,
    Role.OPERATOR: 1,
    Role.MANAGER: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4,
}


# ============================================================================
# PERMISSIONS
# ============================================================================

class Permission(str, Enum):
    # Produtos
    VIEW_PRODUCTS = "view_products"
    MANAGE_PRODUCTS = "manage_products"

    # Ordens de compra
    VIEW_ORDERS = "view_orders"
    CREATE_ORDERS = "create_orders"
    APPROVE_ORDERS = "approve_orders"

    # Fornecedores
    VIEW_SUPPLIERS = "view_suppliers"
    MANAGE_SUPPLIERS = "manage_suppliers"

    # Agentes IA
    USE_AGENT = "use_agent"
    MANAGE_AGENTS = "manage_agents"

    # Usuarios e tenant
    MANAGE_USERS = "manage_users"
    MANAGE_TENANT = "manage_tenant"

    # Admin
    ADMIN_ACCESS = "admin_access"
    VIEW_AUDIT = "view_audit"


# Mapeamento role -> permissions
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_ORDERS,
        Permission.VIEW_SUPPLIERS,
    },
    Role.OPERATOR: {
        Permission.VIEW_PRODUCTS,
        Permission.VIEW_ORDERS,
        Permission.CREATE_ORDERS,
        Permission.VIEW_SUPPLIERS,
        Permission.USE_AGENT,
    },
    Role.MANAGER: {
        Permission.VIEW_PRODUCTS,
        Permission.MANAGE_PRODUCTS,
        Permission.VIEW_ORDERS,
        Permission.CREATE_ORDERS,
        Permission.APPROVE_ORDERS,
        Permission.VIEW_SUPPLIERS,
        Permission.MANAGE_SUPPLIERS,
        Permission.USE_AGENT,
        Permission.MANAGE_AGENTS,
        Permission.VIEW_AUDIT,
    },
    Role.ADMIN: {
        Permission.VIEW_PRODUCTS,
        Permission.MANAGE_PRODUCTS,
        Permission.VIEW_ORDERS,
        Permission.CREATE_ORDERS,
        Permission.APPROVE_ORDERS,
        Permission.VIEW_SUPPLIERS,
        Permission.MANAGE_SUPPLIERS,
        Permission.USE_AGENT,
        Permission.MANAGE_AGENTS,
        Permission.MANAGE_USERS,
        Permission.ADMIN_ACCESS,
        Permission.VIEW_AUDIT,
    },
    Role.OWNER: set(Permission),  # Todas as permissoes
}


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

def require_role(*allowed_roles: str):
    """
    Dependency que exige que o usuario tenha uma role especifica.

    Uso:
        @router.post("/orders")
        async def create_order(user=Depends(require_role("operator", "manager"))):
            ...
    """
    async def _check_role(current_user=Depends(get_current_user)):
        user_role = getattr(current_user, "role", None) or "viewer"

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Role necessaria: {', '.join(allowed_roles)}. Sua role: {user_role}",
            )
        return current_user

    return _check_role


def require_permission(permission: str):
    """
    Dependency que exige que o usuario tenha uma permissao especifica.

    Uso:
        @router.delete("/users/{id}")
        async def delete_user(user=Depends(require_permission("manage_users"))):
            ...
    """
    async def _check_permission(current_user=Depends(get_current_user)):
        user_role_str = getattr(current_user, "role", None) or "viewer"

        try:
            user_role = Role(user_role_str)
        except ValueError:
            user_role = Role.VIEWER

        user_permissions = ROLE_PERMISSIONS.get(user_role, set())

        try:
            required = Permission(permission)
        except ValueError as exc:
            LOGGER.warning(f"Permissao desconhecida requisitada: {permission}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissao invalida",
            ) from exc

        if required not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Permissao necessaria: {permission}",
            )

        return current_user

    return _check_permission


def require_minimum_role(minimum_role: str):
    """
    Dependency que exige role igual ou superior na hierarquia.

    Uso:
        @router.put("/tenant")
        async def update_tenant(user=Depends(require_minimum_role("admin"))):
            ...
    """
    async def _check_hierarchy(current_user=Depends(get_current_user)):
        user_role_str = getattr(current_user, "role", None) or "viewer"

        try:
            user_role = Role(user_role_str)
            min_role = Role(minimum_role)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role invalida",
            ) from exc

        if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY.get(min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Role minima necessaria: {minimum_role}. Sua role: {user_role_str}",
            )

        return current_user

    return _check_hierarchy


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_permissions(role: str) -> set[str]:
    """Retorna set de permissoes para uma role."""
    try:
        r = Role(role)
        return {p.value for p in ROLE_PERMISSIONS.get(r, set())}
    except ValueError:
        return set()


def has_permission(role: str, permission: str) -> bool:
    """Verifica se uma role tem uma permissao."""
    return permission in get_user_permissions(role)
