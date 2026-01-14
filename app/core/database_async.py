"""
Database Engine & Session Management - Full Async Implementation.

ARQUITETURA DE PRODUÇÃO (SaaS Multi-Tenant):
=============================================
Este módulo fornece conexão ASYNC com MySQL usando aiomysql.

CARACTERÍSTICAS:
- 100% Async (aiomysql driver)
- ContextVar para Multi-Tenancy (Row-Level Security)
- Connection Pool otimizado para produção
- Health checks automáticos (pool_pre_ping)

REFERÊNCIAS:
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLModel Async (experimental): https://sqlmodel.tiangolo.com/
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/

MIGRAÇÃO:
- get_session() -> DEPRECATED (manter para compatibilidade)
- get_async_session() -> NOVO PADRÃO

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import os
import logging
import warnings
from typing import Generator, AsyncGenerator, Optional
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, SQLModel, create_engine

from app.core.tenant_context import TenantContext, TenantRequiredError


LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE AMBIENTE
# ============================================================================

def _get_database_url(async_mode: bool = False) -> str:
    """
    Obtém URL do banco de dados das variáveis de ambiente.
    
    Conforme docs SQLAlchemy Async:
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-core
    
    Args:
        async_mode: Se True, retorna URL para driver assíncrono (aiomysql)
        
    Returns:
        str: URL de conexão formatada
        
    Raises:
        RuntimeError: Se DATABASE_URL não estiver configurada em produção
    """
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        if os.getenv("ALLOW_DEFAULT_DB", "false").lower() == "true":
            LOGGER.warning("⚠️ DATABASE_URL não definida. Usando default de dev.")
            database_url = "mysql+pymysql://app_user:app_password@db:3306/app_db"
        else:
            raise RuntimeError(
                "❌ DATABASE_URL não configurada.\n"
                "Configure no .env: DATABASE_URL=mysql+pymysql://user:pass@host:3306/db\n"
                "Para desenvolvimento, defina ALLOW_DEFAULT_DB=true"
            )
    
    # Converte para driver assíncrono
    if async_mode:
        # mysql+pymysql:// -> mysql+aiomysql://
        if "pymysql" in database_url:
            database_url = database_url.replace("pymysql", "aiomysql")
        elif "mysqlconnector" in database_url:
            database_url = database_url.replace("mysqlconnector", "aiomysql")
        elif "mysql://" in database_url and "+aiomysql" not in database_url:
            database_url = database_url.replace("mysql://", "mysql+aiomysql://")
    
    return database_url


# ============================================================================
# ASYNC ENGINE (NOVO PADRÃO - PRODUÇÃO)
# ============================================================================

def create_async_engine_instance() -> AsyncEngine:
    """
    Cria AsyncEngine SQLAlchemy para operações assíncronas.
    
    Configurações de produção otimizadas:
    - pool_pre_ping: Valida conexões antes de usar (evita stale connections)
    - pool_recycle: Recicla conexões a cada 30min (evita timeout MySQL)
    - pool_size: 10 conexões base, max 20 overflow
    
    Conforme docs SQLAlchemy:
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-the-asyncsession
    
    Returns:
        AsyncEngine: Engine configurado para produção
    """
    url = _get_database_url(async_mode=True)
    
    LOGGER.info(f"🔌 Criando AsyncEngine: {url.split('@')[1] if '@' in url else 'hidden'}")
    
    async_engine = create_async_engine(
        url,
        # Pool configuration (produção)
        pool_pre_ping=True,           # Verifica conexão antes de usar
        pool_recycle=1800,            # Recicla a cada 30min
        pool_size=10,                 # Conexões base
        max_overflow=20,              # Conexões extras sob demanda
        pool_timeout=30,              # Timeout para obter conexão
        poolclass=QueuePool,          # Pool com fila (thread-safe)
        
        # Echo SQL para debug (desabilitar em produção)
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        
        # Future mode (SQLAlchemy 2.0 style)
        future=True,
    )
    
    return async_engine


# Singleton do AsyncEngine
_async_engine: Optional[AsyncEngine] = None


def get_async_engine() -> AsyncEngine:
    """
    Obtém singleton do AsyncEngine.
    
    Cria na primeira chamada (lazy initialization).
    """
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine_instance()
    return _async_engine


# AsyncSession factory
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Cria factory de AsyncSession.
    
    Conforme docs SQLAlchemy:
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-async-sessions
    """
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,  # Permite acessar atributos após commit
        autoflush=False,         # Controle manual de flush
    )


# Singleton da factory
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Obtém singleton da AsyncSession factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = get_async_session_factory()
    return _async_session_factory


# ============================================================================
# ASYNC SESSION DEPENDENCY (Para FastAPI)
# ============================================================================

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency que fornece AsyncSession para endpoints FastAPI.
    
    Uso em rotas:
        @router.get("/products")
        async def list_products(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(Product))
            return result.scalars().all()
    
    Conforme docs FastAPI + SQLModel:
    https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/
    
    Yields:
        AsyncSession: Sessão do banco com contexto de tenant
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_async_session_with_tenant() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency que fornece AsyncSession COM verificação de tenant.
    
    Lança TenantRequiredError se não houver tenant no contexto.
    Use para rotas que DEVEM ter tenant (não admin).
    
    Yields:
        AsyncSession: Sessão com tenant validado
        
    Raises:
        TenantRequiredError: Se não houver tenant no contexto
    """
    # Valida tenant antes de criar sessão
    TenantContext.require_tenant()
    
    async for session in get_async_session():
        yield session


# ============================================================================
# ENGINE SÍNCRONO (DEPRECATED - Manter para compatibilidade)
# ============================================================================

def create_sync_engine_instance() -> Engine:
    """
    Cria engine SQLModel síncrono (DEPRECATED).
    
    ⚠️ AVISO: Use get_async_session() para novos endpoints.
    Este método existe apenas para compatibilidade com código legado.
    """
    warnings.warn(
        "create_sync_engine_instance() está DEPRECATED. "
        "Use get_async_session() para novos endpoints.",
        DeprecationWarning,
        stacklevel=2
    )
    
    url = _get_database_url(async_mode=False)
    
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )


# Singleton do engine síncrono (lazy, só cria se usar)
_sync_engine: Optional[Engine] = None


def get_sync_engine() -> Engine:
    """
    Obtém singleton do Engine síncrono (DEPRECATED).
    """
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_sync_engine_instance()
    return _sync_engine


# Alias para compatibilidade com código existente
engine = property(lambda self: get_sync_engine())


def get_session() -> Generator[Session, None, None]:
    """
    Dependency síncrona (DEPRECATED).
    
    ⚠️ AVISO: Use get_async_session() para novos endpoints.
    
    Yields:
        Session: Sessão síncrona do SQLModel
    """
    warnings.warn(
        "get_session() está DEPRECATED. Use get_async_session().",
        DeprecationWarning,
        stacklevel=2
    )
    
    with Session(get_sync_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# Para importação direta: from app.core.database import engine
# Lazy loading via __getattr__
def __getattr__(name: str):
    """Lazy loading para 'engine' (compatibilidade)."""
    if name == "engine":
        return get_sync_engine()
    raise AttributeError(f"module 'app.core.database' has no attribute '{name}'")


# ============================================================================
# INICIALIZAÇÃO DE TABELAS
# ============================================================================

async def init_db() -> None:
    """
    Inicializa banco de dados (cria tabelas se não existirem).
    
    Chamado no startup da aplicação.
    """
    LOGGER.info("📦 Inicializando banco de dados...")
    
    async_engine = get_async_engine()
    
    async with async_engine.begin() as conn:
        # Cria todas as tabelas definidas em SQLModel.metadata
        await conn.run_sync(SQLModel.metadata.create_all)
    
    LOGGER.info("✅ Banco de dados inicializado")


async def close_db() -> None:
    """
    Fecha conexões do banco de dados.
    
    Chamado no shutdown da aplicação.
    """
    global _async_engine, _sync_engine
    
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        LOGGER.info("🔌 AsyncEngine fechado")
    
    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None
        LOGGER.info("🔌 SyncEngine fechado")


# ============================================================================
# HEALTH CHECK
# ============================================================================

async def check_database_health() -> dict:
    """
    Verifica saúde da conexão com o banco.
    
    Returns:
        dict: Status da conexão
    """
    try:
        async with get_session_factory()() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        
        return {
            "status": "healthy",
            "database": "connected",
            "driver": "aiomysql"
        }
    except Exception as e:
        LOGGER.error(f"❌ Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
