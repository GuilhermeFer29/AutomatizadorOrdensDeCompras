"""
Tenant Context Management - Row-Level Security Implementation.

Este módulo fornece o mecanismo de isolamento de dados Multi-Tenant
usando ContextVar para propagação segura do tenant_id através de
chamadas assíncronas e síncronas.

REFERÊNCIAS:
- Python contextvars: https://docs.python.org/3/library/contextvars.html
- FastAPI Middleware: https://fastapi.tiangolo.com/tutorial/middleware/
- SQLAlchemy Events: https://docs.sqlalchemy.org/en/20/core/event.html

SEGURANÇA:
- ContextVar garante isolamento entre requests concorrentes
- Cada request tem seu próprio contexto de tenant
- Queries automáticas com WHERE tenant_id = X

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any
from uuid import UUID

LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONTEXT VARIABLES (Thread-Safe, Async-Safe)
# ============================================================================

# ContextVar para armazenar tenant_id do request atual
# Conforme docs Python: https://docs.python.org/3/library/contextvars.html
_current_tenant_id: ContextVar[UUID | None] = ContextVar(
    "current_tenant_id",
    default=None
)

# ContextVar para armazenar user_id (opcional, para audit logs)
_current_user_id: ContextVar[int | None] = ContextVar(
    "current_user_id",
    default=None
)


# ============================================================================
# TENANT CONTEXT MANAGER
# ============================================================================

class TenantContext:
    """
    Gerenciador de contexto para Multi-Tenancy.

    Uso em Middleware:
        @app.middleware("http")
        async def tenant_middleware(request, call_next):
            tenant_id = extract_tenant_from_request(request)
            with TenantContext(tenant_id):
                return await call_next(request)

    Uso em Endpoints:
        tenant_id = TenantContext.get_current_tenant()
    """

    def __init__(self, tenant_id: UUID | None, user_id: int | None = None):
        """
        Inicializa contexto de tenant.

        Args:
            tenant_id: UUID do tenant (pode ser None para admin/superuser)
            user_id: ID do usuário logado (opcional)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._tenant_token = None
        self._user_token = None

    def __enter__(self) -> TenantContext:
        """Entra no contexto, setando tenant e user."""
        self._tenant_token = _current_tenant_id.set(self.tenant_id)
        if self.user_id:
            self._user_token = _current_user_id.set(self.user_id)

        LOGGER.debug(f"TenantContext entered: tenant={self.tenant_id}, user={self.user_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sai do contexto, resetando tokens."""
        if self._tenant_token:
            _current_tenant_id.reset(self._tenant_token)
        if self._user_token:
            _current_user_id.reset(self._user_token)

        LOGGER.debug("TenantContext exited")
        return False  # Não suprime exceções

    async def __aenter__(self) -> TenantContext:
        """Versão async do enter."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Versão async do exit."""
        return self.__exit__(exc_type, exc_val, exc_tb)

    # ========================================================================
    # STATIC METHODS (Para acesso global)
    # ========================================================================

    @staticmethod
    def get_current_tenant() -> UUID | None:
        """
        Obtém o tenant_id do contexto atual.

        Returns:
            UUID do tenant ou None se não estiver em contexto de tenant.
        """
        return _current_tenant_id.get()

    @staticmethod
    def get_current_user() -> int | None:
        """
        Obtém o user_id do contexto atual.

        Returns:
            ID do usuário ou None.
        """
        return _current_user_id.get()

    @staticmethod
    def require_tenant() -> UUID:
        """
        Obtém tenant_id, lançando exceção se não existir.

        Use em rotas que DEVEM ter tenant (não admin).

        Returns:
            UUID do tenant.

        Raises:
            TenantRequiredError: Se não houver tenant no contexto.
        """
        tenant_id = _current_tenant_id.get()
        if tenant_id is None:
            raise TenantRequiredError(
                "Operação requer contexto de tenant. "
                "Verifique se o middleware está ativo."
            )
        return tenant_id

    @staticmethod
    def is_superuser() -> bool:
        """
        Verifica se o contexto atual é de superuser (sem tenant).

        Superusers podem ver dados de todos os tenants.

        Returns:
            True se não houver tenant_id no contexto.
        """
        return _current_tenant_id.get() is None


# ============================================================================
# EXCEPTIONS
# ============================================================================

class TenantRequiredError(Exception):
    """Exceção quando operação requer tenant mas não há no contexto."""
    pass


class TenantMismatchError(Exception):
    """Exceção quando há tentativa de acessar dados de outro tenant."""
    pass


# ============================================================================
# DECORATORS
# ============================================================================

def require_tenant_context(func: Callable) -> Callable:
    """
    Decorator que garante que função só executa em contexto de tenant.

    Uso:
        @require_tenant_context
        def get_products():
            tenant = TenantContext.get_current_tenant()
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        TenantContext.require_tenant()  # Lança se não houver tenant
        return func(*args, **kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        TenantContext.require_tenant()
        return await func(*args, **kwargs)

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return wrapper


def with_tenant(tenant_id: UUID) -> Callable:
    """
    Decorator que executa função em contexto de tenant específico.

    Útil para tasks Celery que precisam de contexto.

    Uso:
        @with_tenant(some_tenant_id)
        def celery_task():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with TenantContext(tenant_id):
                return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with TenantContext(tenant_id):
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def run_in_tenant_context(
    tenant_id: UUID,
    func: Callable,
    *args,
    **kwargs
) -> Any:
    """
    Executa função em contexto de tenant específico.

    Útil para Celery tasks que recebem tenant_id como parâmetro.

    Args:
        tenant_id: UUID do tenant
        func: Função a executar
        *args, **kwargs: Argumentos da função

    Returns:
        Resultado da função.

    Example:
        result = run_in_tenant_context(
            tenant_id=uuid.UUID("..."),
            func=process_orders,
            order_ids=[1, 2, 3]
        )
    """
    with TenantContext(tenant_id):
        return func(*args, **kwargs)
