"""
Database Engine & Session Management - Hybrid Async/Sync.

ARQUITETURA:
- get_async_session() -> NOVO PADRÃO (async)
- get_session() -> Compatibilidade (sync)
- create_db_and_tables() -> Startup sync

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

LOGGER = logging.getLogger(__name__)


# ============================================================================
# DATABASE URL
# ============================================================================

def _get_database_url(async_mode: bool = False) -> str:
    """Obtém URL do banco das variáveis de ambiente."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        if os.getenv("ALLOW_DEFAULT_DB", "false").lower() == "true":
            LOGGER.warning("DATABASE_URL não definida. Usando default de dev.")
            database_url = "mysql+pymysql://app_user:app_password@db:3306/app_db"
        else:
            raise RuntimeError("DATABASE_URL não configurada.")

    # Converte qualquer driver MySQL síncrono para aiomysql (async)
    if async_mode and database_url.startswith("mysql+"):
        # Suporta: mysql+pymysql, mysql+mysqlconnector, mysql+mysqldb, etc.
        import re
        database_url = re.sub(r'^mysql\+\w+://', 'mysql+aiomysql://', database_url)

    return database_url


# ============================================================================
# SYNC ENGINE (Compatibilidade e Startup)
# ============================================================================

_sync_engine: Engine | None = None


def get_sync_engine() -> Engine:
    """Retorna engine síncrono (singleton)."""
    global _sync_engine
    if _sync_engine is None:
        url = _get_database_url(async_mode=False)
        kwargs: dict = {
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
        }
        # SQLite não suporta pool_size / max_overflow / pool_recycle
        if not url.startswith("sqlite"):
            kwargs.update(
                pool_pre_ping=True,
                pool_recycle=1800,
                pool_size=5,
                max_overflow=10,
            )
        else:
            from sqlmodel.pool import StaticPool
            kwargs.update(
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        _sync_engine = create_engine(url, **kwargs)
    return _sync_engine


# Alias para compatibilidade (lazy evaluation)
class _EngineProxy:
    """Proxy para engine com lazy initialization."""
    def __getattr__(self, name):
        return getattr(get_sync_engine(), name)

    def __repr__(self):
        return repr(get_sync_engine())

engine = _EngineProxy()


def get_session() -> Generator[Session, None, None]:
    """Dependency síncrona para FastAPI."""
    with Session(get_sync_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_db_and_tables() -> None:
    """
    Cria tabelas do banco com retry e exponential backoff.
    Usado no startup da aplicação.
    """
    max_retries = 5
    retry_delay = 2

    # Importa todos os models para registrar no metadata
    from app.models import models  # noqa: F401

    eng = get_sync_engine()

    for attempt in range(max_retries):
        try:
            SQLModel.metadata.create_all(eng)
            LOGGER.info("✅ Tabelas do banco criadas/verificadas")
            return
        except OperationalError as e:
            if attempt < max_retries - 1:
                LOGGER.warning(
                    f"Conexão falhou (tentativa {attempt + 1}/{max_retries}). "
                    f"Retry em {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                LOGGER.error(f"Falha após {max_retries} tentativas")
                raise e


# ============================================================================
# ASYNC ENGINE (Novo Padrão)
# ============================================================================

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    """Retorna AsyncEngine (singleton)."""
    global _async_engine
    if _async_engine is None:
        # Detecta se está em worker Celery (multiprocessing + event loops)
        is_celery = os.getenv("CELERY_BROKER_URL") is not None
        
        engine_kwargs = {
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
        }
        
        if is_celery:
            # Celery workers: sem pooling (evita event loop cleanup issues)
            # NullPool cria/fecha conexão a cada requisição
            LOGGER.info("🔧 Async engine: NullPool (Celery worker mode)")
            engine_kwargs["poolclass"] = NullPool
        else:
            # API/outros: pooling normal para performance
            LOGGER.info("🔧 Async engine: AsyncPool (normal mode)")
            engine_kwargs.update({
                "pool_pre_ping": True,
                "pool_recycle": 1800,
                "pool_size": 10,
                "max_overflow": 20,
            })
        
        _async_engine = create_async_engine(
            _get_database_url(async_mode=True),
            **engine_kwargs,
        )
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retorna factory de AsyncSession (singleton)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency assíncrona para FastAPI."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ============================================================================
# LIFECYCLE
# ============================================================================

async def init_db() -> None:
    """Inicializa banco de dados (async)."""
    from app.models import models  # noqa: F401

    async_eng = get_async_engine()
    async with async_eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    LOGGER.info("✅ Banco inicializado (async)")


async def close_db() -> None:
    """Fecha conexões do banco."""
    global _async_engine, _sync_engine

    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None

    if _sync_engine:
        _sync_engine.dispose()
        _sync_engine = None


async def check_database_health() -> dict:
    """Health check do banco."""
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ============================================================================
# EXPORTS
# ============================================================================

def __getattr__(name: str):
    """Lazy loading para 'engine'."""
    if name == "engine":
        return get_sync_engine()
    raise AttributeError(f"module has no attribute '{name}'")


__all__ = [
    "engine",
    "get_session",
    "get_async_session",
    "get_sync_engine",
    "get_async_engine",
    "get_session_factory",
    "create_db_and_tables",
    "init_db",
    "close_db",
    "check_database_health",
]
