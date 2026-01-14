"""
Database engine and session management utilities.

ARQUITETURA DE PRODUÇÃO:
========================
Este módulo fornece conexão com o banco de dados MySQL.

MODO HÍBRIDO:
- get_session(): Sessão SÍNCRONA (compatibilidade com código existente)
- get_async_session(): Sessão ASSÍNCRONA (para novos endpoints)

SEGURANÇA (Crash-Only Software):
- Se DATABASE_URL não estiver definida, o app FALHA no startup
- Sem credenciais default hardcoded em produção

REFERÊNCIAS:
- SQLModel Async: https://sqlmodel.tiangolo.com/tutorial/connect/create-connected-tables/
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import os
import logging
import time
from typing import Generator, AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

LOGGER = logging.getLogger(__name__)


# ============================================================================
# VALIDAÇÃO DE AMBIENTE (Crash-Only Software)
# ============================================================================

def _get_database_url(async_mode: bool = False) -> str:
    """
    Obtém a URL do banco de dados das variáveis de ambiente.
    
    Args:
        async_mode: Se True, retorna URL para driver assíncrono (aiomysql)
        
    Returns:
        str: URL de conexão formatada
        
    Raises:
        RuntimeError: Se DATABASE_URL não estiver configurada em produção
    """
    # Tenta obter do ambiente
    database_url = os.getenv("DATABASE_URL")
    
    # Em produção (ou se explicitamente configurado), exige variável
    if not database_url:
        # Fallback para desenvolvimento local APENAS se explicitamente permitido
        if os.getenv("ALLOW_DEFAULT_DB", "false").lower() == "true":
            LOGGER.warning(
                "⚠️ DATABASE_URL não definida. Usando default de desenvolvimento."
            )
            database_url = "mysql+pymysql://app_user:app_password@db:3306/app_db"
        else:
            raise RuntimeError(
                "❌ DATABASE_URL não configurada.\n"
                "Configure no .env: DATABASE_URL=mysql+pymysql://user:pass@host:3306/db\n"
                "Para desenvolvimento, defina ALLOW_DEFAULT_DB=true"
            )
    
    # Converte para driver assíncrono se necessário
    if async_mode:
        # mysql+pymysql:// -> mysql+aiomysql://
        # mysql+mysqlconnector:// -> mysql+aiomysql://
        if "pymysql" in database_url:
            database_url = database_url.replace("pymysql", "aiomysql")
        elif "mysqlconnector" in database_url:
            database_url = database_url.replace("mysqlconnector", "aiomysql")
        elif "mysql://" in database_url and "+aiomysql" not in database_url:
            database_url = database_url.replace("mysql://", "mysql+aiomysql://")
    
    return database_url


# ============================================================================
# ENGINE SÍNCRONO (Compatibilidade com código existente)
# ============================================================================

def create_engine_instance() -> Engine:
    """
    Cria engine SQLModel síncrono para operações tradicionais.
    
    Configurações de produção:
    - pool_pre_ping: Valida conexões antes de usar
    - pool_recycle: Recicla conexões a cada 30min
    - pool_size: 5 conexões base, max 10
    """
    return create_engine(
        _get_database_url(async_mode=False),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,  # 30 minutos
        pool_size=5,
        max_overflow=5,
    )


# Engine global (lazy initialization)
_sync_engine: Engine | None = None


def get_sync_engine() -> Engine:
    """Retorna o engine síncrono (lazy init)."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine_instance()
    return _sync_engine


# Alias para compatibilidade
engine: Engine = property(lambda self: get_sync_engine())


# ============================================================================
# ENGINE ASSÍNCRONO (Para novos endpoints de alta performance)
# ============================================================================

def create_async_engine_instance() -> AsyncEngine:
    """
    Cria engine assíncrono para operações non-blocking.
    
    Requer: aiomysql instalado (`pip install aiomysql`)
    """
    return create_async_engine(
        _get_database_url(async_mode=True),
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
    )


# Engine assíncrono global (lazy initialization)
_async_engine: AsyncEngine | None = None


def get_async_engine() -> AsyncEngine:
    """Retorna o engine assíncrono (lazy init)."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine_instance()
    return _async_engine


# ============================================================================
# SESSION FACTORIES
# ============================================================================

def get_session() -> Generator[Session, None, None]:
    """
    Dependency injection para sessão SÍNCRONA.
    
    Uso com FastAPI:
        @app.get("/items")
        def get_items(session: Session = Depends(get_session)):
            ...
    """
    engine = get_sync_engine()
    with Session(engine) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection para sessão ASSÍNCRONA.
    
    Uso com FastAPI:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async_session = sessionmaker(
        get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session() as session:
        yield session


# ============================================================================
# CRIAÇÃO DE TABELAS
# ============================================================================

def create_db_and_tables() -> None:
    """
    Cria tabelas do banco de dados com retry e exponential backoff.
    
    Usado no startup da aplicação.
    """
    max_retries = 5
    retry_delay = 2
    
    engine = get_sync_engine()
    
    for attempt in range(max_retries):
        try:
            SQLModel.metadata.create_all(engine)
            LOGGER.info("✅ Database tables created successfully")
            return
        except OperationalError as e:
            if attempt < max_retries - 1:
                LOGGER.warning(
                    "Database connection failed (attempt %d/%d). Retrying in %ds...",
                    attempt + 1,
                    max_retries,
                    retry_delay,
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                LOGGER.error("Failed to connect to database after %d attempts", max_retries)
                raise e


async def create_db_and_tables_async() -> None:
    """
    Versão assíncrona da criação de tabelas.
    
    Nota: SQLModel ainda não suporta create_all async nativamente,
    então isso é um wrapper que executa em thread separada.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_db_and_tables)


# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_database_health() -> dict:
    """
    Verifica saúde da conexão com o banco de dados.
    
    Returns:
        dict: Status da conexão
    """
    try:
        engine = get_sync_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


# ============================================================================
# EXPORTS
# ============================================================================

# Para compatibilidade, exportamos o engine como propriedade lazy
def __getattr__(name: str):
    """Lazy loading do engine para compatibilidade."""
    if name == "engine":
        return get_sync_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_session",
    "get_async_session", 
    "get_sync_engine",
    "get_async_engine",
    "create_db_and_tables",
    "create_db_and_tables_async",
    "check_database_health",
]
