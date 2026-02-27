"""
FastAPI Application Entrypoint - SaaS Multi-Tenant Edition.

ARQUITETURA DE PRODUÇÃO:
========================
- Multi-Tenancy: Isolamento de dados por tenant via JWT
- Observabilidade: Prometheus metrics em /metrics
- Cache: Redis com fastapi-cache2
- CORS: Configurado via variáveis de ambiente

MIDDLEWARES (ordem de execução):
1. PrometheusMiddleware (métricas)
2. TenantMiddleware (extrai tenant do JWT)
3. CORSMiddleware (cross-origin)

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import create_db_and_tables

load_dotenv()
LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE AMBIENTE
# ============================================================================

def _get_allowed_origins() -> list[str]:
    """Obtém lista de origens permitidas para CORS."""

    environment = os.getenv("APP_ENV", "development")

    # CORS_ALLOW_ALL=true libera para qualquer origem (APENAS DESENVOLVIMENTO!)
    if os.getenv("CORS_ALLOW_ALL", "false").lower() == "true":
        if environment == "production":
            LOGGER.error(
                "CORS_ALLOW_ALL=true em PRODUCAO! Ignorando. "
                "Configure ALLOWED_ORIGINS corretamente."
            )
        else:
            LOGGER.warning("CORS: LIBERADO PARA TODAS AS ORIGENS (dev only)")
            return ["*"]

    origins_env = os.getenv("ALLOWED_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",")]

    frontend_url = os.getenv("FRONTEND_URL", "")
    if frontend_url:
        return [frontend_url]

    if os.getenv("ALLOW_DEV_CORS", "true").lower() == "true" and environment != "production":
        LOGGER.warning("CORS: Usando origens de desenvolvimento.")
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
        ]

    return []


# ============================================================================
# LIFESPAN (Startup/Shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação."""

    # ====== STARTUP ======
    LOGGER.info("🚀 Iniciando aplicação SaaS Multi-Tenant...")

    # 1. Cria tabelas do banco de dados
    try:
        create_db_and_tables()
        LOGGER.info("✅ Tabelas do banco criadas/verificadas")
    except Exception as e:
        LOGGER.error(f"❌ Falha ao criar tabelas: {e}")
        raise

    # 2. Inicializa cache Redis
    try:
        from app.core.cache import init_cache
        await init_cache()
    except Exception as e:
        LOGGER.warning(f"⚠️ Cache não disponível: {e}")

    # 3. Inicia listener Redis (WebSocket)
    try:
        from app.services.redis_events import redis_events
        from app.services.websocket_manager import websocket_manager

        await redis_events.connect()

        async def handle_redis_message(session_id: int, message_data: dict):
            await websocket_manager.send_message(session_id, message_data)

        await redis_events.start_listening(handle_redis_message)
        LOGGER.info("✅ Redis listener iniciado")
    except Exception as e:
        LOGGER.warning(f"⚠️ Redis listener não disponível: {e}")

    LOGGER.info("✅ Aplicação pronta!")
    LOGGER.info("📊 Métricas: http://localhost:8000/metrics")
    LOGGER.info("💡 Para sincronizar RAG: POST /admin/rag/sync")

    yield  # ====== APP RUNNING ======

    # ====== SHUTDOWN ======
    LOGGER.info("🛑 Encerrando aplicação...")

    try:
        from app.services.redis_events import redis_events
        await redis_events.disconnect()
    except Exception as e:
        LOGGER.debug(f"Redis disconnect during shutdown: {e}")


# ============================================================================
# FACTORY DE APLICAÇÃO
# ============================================================================

def create_application() -> FastAPI:
    """Constrói e configura a instância FastAPI."""

    application = FastAPI(
        title="PMI - Automação de Ordens de Compra",
        description=(
            "API SaaS Multi-Tenant para automação de compras industriais com IA. "
            "Utiliza Google Gemini, RAG e ML para recomendações inteligentes."
        ),
        version="2.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ====== PROMETHEUS METRICS ======
    if os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true":
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator().instrument(application).expose(application)
            LOGGER.info("✅ Prometheus metrics habilitadas em /metrics")
        except ImportError as e:
            LOGGER.warning(f"⚠️ prometheus-fastapi-instrumentator não instalado: {e}")
        except Exception as e:
            LOGGER.error(f"❌ Erro ao configurar Prometheus: {e}")

    # ====== TENANT MIDDLEWARE ======
    try:
        from app.core.tenant import TenantMiddleware
        application.add_middleware(TenantMiddleware)
        LOGGER.info("✅ Multi-Tenancy middleware ativado")
    except ImportError as e:
        LOGGER.warning(f"⚠️ TenantMiddleware não disponível: {e}")

    # ====== CORS ======
    allowed_origins = _get_allowed_origins()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    LOGGER.info(f"🔒 CORS configurado para: {allowed_origins}")

    # ====== ROUTERS ======
    _register_routers(application)

    # ====== EXCEPTION HANDLERS ======
    _register_exception_handlers(application)

    # ====== HEALTH CHECK ======
    @application.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, Any]:
        """Health check para readiness probes."""
        return {"status": "ok", "version": "2.1.0"}

    return application


def _register_routers(app: FastAPI) -> None:
    """Registra todos os routers da aplicação."""

    # Routers principais
    from app.routers.agent_router import router as agent_router
    from app.routers.ml_router import router as ml_router
    from app.routers.sales_router import router as sales_router
    from app.routers.tasks_router import router as tasks_router

    app.include_router(tasks_router)
    app.include_router(sales_router)
    app.include_router(ml_router)
    app.include_router(agent_router)

    # API Routers (Frontend)
    from app.routers import (
        api_agent_router,
        api_audit_router,
        api_chat_router,
        api_dashboard_router,
        api_order_router,
        api_product_router,
        api_supplier_router,
    )

    app.include_router(api_dashboard_router.router)
    app.include_router(api_product_router.router)
    app.include_router(api_agent_router.router)
    app.include_router(api_order_router.router)
    app.include_router(api_chat_router.router)
    app.include_router(api_supplier_router.router)
    app.include_router(api_audit_router.router)

    # RAG Router
    from app.routers.rag_router import router as rag_router
    app.include_router(rag_router)

    # Auth Router
    from app.routers.auth_router import router as auth_router
    app.include_router(auth_router)

    # Admin Router
    from app.routers.admin_router import router as admin_router
    app.include_router(admin_router)


def _register_exception_handlers(app: FastAPI) -> None:
    """Registra handlers de exceção padronizados."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path)
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Sanitiza errors para JSON: ctx pode conter objetos não-serializáveis
        safe_errors = []
        for err in exc.errors():
            safe_err = {**err}
            if "ctx" in safe_err and isinstance(safe_err["ctx"], dict):
                safe_err["ctx"] = {
                    k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                    for k, v in safe_err["ctx"].items()
                }
            safe_errors.append(safe_err)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": 422,
                "message": "Dados de entrada inválidos",
                "details": safe_errors,
                "path": str(request.url.path)
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        LOGGER.exception(f"Erro não tratado: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "status_code": 500,
                "message": "Erro interno do servidor",
                "path": str(request.url.path)
            }
        )


# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

app: FastAPI = create_application()
