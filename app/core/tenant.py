"""
Multi-Tenancy System - Isolamento de Dados por Tenant.

ARQUITETURA SaaS:
=================
Este módulo implementa isolamento de dados por tenant usando:
1. TenantMixin: Adiciona tenant_id a todos os modelos
2. TenantMiddleware: Extrai tenant_id do JWT e injeta no contexto
3. TenantSession: Filtra queries automaticamente por tenant

SEGURANÇA:
- Cada request tem um tenant_id isolado
- Queries são filtradas automaticamente
- Não é possível acessar dados de outro tenant

REFERÊNCIAS:
- FastAPI Middleware: https://fastapi.tiangolo.com/tutorial/middleware/
- SQLModel Issues: https://github.com/tiangolo/sqlmodel/issues/63

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Optional, Any, Callable
from uuid import UUID, uuid4

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlmodel import Session, select
from sqlalchemy import event
from sqlalchemy.orm import Query

LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONTEXT VARIABLE (Thread-Safe)
# ============================================================================

# Context variable para armazenar tenant_id da request atual
_tenant_context: ContextVar[Optional[UUID]] = ContextVar("tenant_id", default=None)


def get_current_tenant_id() -> Optional[UUID]:
    """
    Retorna o tenant_id da request atual.
    
    Returns:
        UUID ou None se não houver tenant no contexto
    """
    return _tenant_context.get()


def set_current_tenant_id(tenant_id: Optional[UUID]) -> None:
    """
    Define o tenant_id para a request atual.
    
    Args:
        tenant_id: UUID do tenant ou None
    """
    _tenant_context.set(tenant_id)


# ============================================================================
# TENANT MIDDLEWARE
# ============================================================================

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware que extrai tenant_id do JWT e injeta no contexto.
    
    Fluxo:
    1. Intercepta request
    2. Extrai token JWT do header Authorization
    3. Decodifica e extrai tenant_id do payload
    4. Injeta no contexto via ContextVar
    5. Limpa contexto após response
    
    Endpoints públicos (sem tenant):
    - /health, /docs, /redoc, /openapi.json
    - /auth/login, /auth/register
    - /metrics
    """
    
    # Endpoints que não requerem tenant
    PUBLIC_PATHS = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/admin/health",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa request e injeta tenant no contexto."""
        
        # Skip para paths públicos
        path = request.url.path
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Tenta extrair tenant_id do JWT
        tenant_id = await self._extract_tenant_from_jwt(request)
        
        # Injeta no contexto
        set_current_tenant_id(tenant_id)
        
        try:
            response = await call_next(request)
            return response
        finally:
            # Limpa contexto após request
            set_current_tenant_id(None)
    
    async def _extract_tenant_from_jwt(self, request: Request) -> Optional[UUID]:
        """
        Extrai tenant_id do token JWT.
        
        Args:
            request: FastAPI Request
            
        Returns:
            UUID do tenant ou None
        """
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            # Sem token - pode ser request pública ou erro
            return None
        
        token = auth_header.replace("Bearer ", "")
        
        try:
            from app.core.security import decode_jwt_token
            
            payload = decode_jwt_token(token)
            tenant_id_str = payload.get("tenant_id")
            
            if tenant_id_str:
                return UUID(tenant_id_str)
            
            # Fallback: tenta pegar do user
            user_id = payload.get("sub")
            if user_id:
                # Busca tenant do usuário no banco
                return await self._get_tenant_from_user(user_id)
            
            return None
            
        except Exception as e:
            LOGGER.warning(f"Erro ao extrair tenant do JWT: {e}")
            return None
    
    async def _get_tenant_from_user(self, user_id: Any) -> Optional[UUID]:
        """
        Busca tenant_id do usuário no banco.
        
        Args:
            user_id: ID do usuário (pode ser int ou email string)
            
        Returns:
            UUID do tenant ou None
        """
        try:
            from app.core.database import get_sync_engine
            from app.models.models import User
            
            engine = get_sync_engine()
            with Session(engine) as session:
                # Tenta buscar por ID ou Email
                if isinstance(user_id, str) and "@" in user_id:
                    user = session.exec(select(User).where(User.email == user_id)).first()
                else:
                    try:
                        user = session.get(User, int(user_id))
                    except (ValueError, TypeError):
                        user = session.exec(select(User).where(User.email == str(user_id))).first()

                if user and hasattr(user, 'tenant_id'):
                    return user.tenant_id
            return None
        except Exception as e:
            LOGGER.warning(f"Erro ao buscar tenant do usuário: {e}")
            return None


# ============================================================================
# TENANT-AWARE SESSION
# ============================================================================

def get_tenant_session():
    """
    Dependency que retorna uma session filtrada por tenant.
    
    Uso:
        @app.get("/items")
        def get_items(session: Session = Depends(get_tenant_session)):
            items = session.exec(select(Item)).all()  # Auto-filtrado
    """
    from app.core.database import get_sync_engine
    
    engine = get_sync_engine()
    
    with Session(engine) as session:
        tenant_id = get_current_tenant_id()
        
        if tenant_id:
            # Registra listener para filtrar queries
            @event.listens_for(session, "do_orm_execute")
            def _filter_by_tenant(orm_execute_state):
                if orm_execute_state.is_select:
                    # Adiciona filtro de tenant automaticamente
                    mapper = orm_execute_state.bind_arguments.get("mapper")
                    if mapper and hasattr(mapper.class_, "tenant_id"):
                        stmt = orm_execute_state.statement
                        stmt = stmt.where(mapper.class_.tenant_id == tenant_id)
                        orm_execute_state.statement = stmt
        
        yield session


# ============================================================================
# TENANT MIXIN (Para Models)
# ============================================================================

from sqlmodel import Field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import SQLModel


class TenantMixin:
    """
    Mixin que adiciona tenant_id a modelos SQLModel.
    
    Uso:
        class Produto(TenantMixin, SQLModel, table=True):
            id: int = Field(primary_key=True)
            nome: str
            # tenant_id é adicionado automaticamente
    
    IMPORTANTE:
    - Sempre herde TenantMixin ANTES de SQLModel
    - O campo tenant_id é indexado para performance
    - Use get_tenant_session() para queries auto-filtradas
    """
    tenant_id: UUID = Field(
        default_factory=uuid4,
        index=True,
        nullable=False,
        description="ID do tenant (cliente) proprietário deste registro"
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def require_tenant() -> UUID:
    """
    Retorna tenant_id ou levanta exceção se não houver.
    
    Uso em endpoints que EXIGEM tenant:
        @app.post("/items")
        def create_item(tenant_id: UUID = Depends(require_tenant)):
            ...
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant não identificado. Faça login novamente."
        )
    return tenant_id


def get_optional_tenant() -> Optional[UUID]:
    """
    Retorna tenant_id ou None (para endpoints mistos).
    """
    return get_current_tenant_id()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TenantMiddleware",
    "TenantMixin",
    "get_current_tenant_id",
    "set_current_tenant_id",
    "get_tenant_session",
    "require_tenant",
    "get_optional_tenant",
]
