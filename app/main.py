"""
FastAPI Application Entrypoint - Produção.

ARQUITETURA DE PRODUÇÃO:
========================
- Startup LIMPO: Sem indexação bloqueante (movida para /admin/rag/sync)
- CORS SEGURO: Lê origens permitidas do .env
- Fail-Fast: Valida configurações críticas no startup
- Erros Padronizados: HTTP 400, 401, 403, 422, 500 (sem 418)

SEGURANÇA:
- CORS configurado via ALLOWED_ORIGINS
- Credenciais não hardcoded
- Health check sem exposição de dados sensíveis

REFERÊNCIAS:
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import create_db_and_tables

load_dotenv()
LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE AMBIENTE
# ============================================================================

def _get_allowed_origins() -> List[str]:
    """
    Obtém lista de origens permitidas para CORS.
    
    Prioridade:
    1. ALLOWED_ORIGINS (lista separada por vírgula)
    2. FRONTEND_URL (single origin)
    3. Default de desenvolvimento (se ALLOW_DEV_CORS=true)
    
    Returns:
        List[str]: Lista de origens permitidas
    """
    # Tenta lista completa
    origins_env = os.getenv("ALLOWED_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",")]
    
    # Tenta single frontend URL
    frontend_url = os.getenv("FRONTEND_URL", "")
    if frontend_url:
        return [frontend_url]
    
    # Fallback para desenvolvimento
    if os.getenv("ALLOW_DEV_CORS", "true").lower() == "true":
        LOGGER.warning(
            "⚠️ CORS: Usando origens de desenvolvimento. "
            "Configure ALLOWED_ORIGINS ou FRONTEND_URL em produção."
        )
        return [
            "http://localhost:5173",  # Vite dev
            "http://localhost:3000",  # React dev
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]
    
    # Em produção sem configuração: nenhuma origem permitida
    LOGGER.error("❌ CORS: Nenhuma origem configurada. Frontend não funcionará.")
    return []


# ============================================================================
# LIFESPAN (Startup/Shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicação.
    
    STARTUP (Limpo):
    - Cria tabelas do banco (retry com backoff)
    - NÃO faz indexação RAG (usar /admin/rag/sync)
    - Inicia listeners de eventos
    
    SHUTDOWN:
    - Desconecta listeners
    - Fecha conexões
    """
    # ====== STARTUP ======
    LOGGER.info("🚀 Iniciando aplicação...")
    
    # 1. Cria tabelas do banco de dados
    try:
        create_db_and_tables()
        LOGGER.info("✅ Tabelas do banco criadas/verificadas")
    except Exception as e:
        LOGGER.error(f"❌ Falha ao criar tabelas: {e}")
        raise
    
    # 2. Inicia listener Redis (para notificações WebSocket)
    try:
        from app.services.redis_events import redis_events
        from app.services.websocket_manager import websocket_manager
        
        await redis_events.connect()
        
        async def handle_redis_message(session_id: int, message_data: dict):
            LOGGER.debug(f"📥 Redis → WebSocket: session_id={session_id}")
            await websocket_manager.send_message(session_id, message_data)
        
        await redis_events.start_listening(handle_redis_message)
        LOGGER.info("✅ Redis listener iniciado")
    except Exception as e:
        LOGGER.warning(f"⚠️ Redis listener não disponível: {e}")
    
    # 3. Log de inicialização (SEM indexação RAG)
    LOGGER.info("✅ Aplicação pronta!")
    LOGGER.info("💡 Para sincronizar RAG, chame POST /admin/rag/sync")
    
    yield  # ====== APP RUNNING ======
    
    # ====== SHUTDOWN ======
    LOGGER.info("🛑 Encerrando aplicação...")
    
    try:
        from app.services.redis_events import redis_events
        await redis_events.disconnect()
        LOGGER.info("Redis desconectado")
    except Exception as e:
        LOGGER.warning(f"Erro ao desconectar Redis: {e}")


# ============================================================================
# FACTORY DE APLICAÇÃO
# ============================================================================

def create_application() -> FastAPI:
    """
    Constrói e configura a instância FastAPI.
    
    Returns:
        FastAPI: Aplicação configurada
    """
    application = FastAPI(
        title="Automação Inteligente de Ordens de Compra",
        description=(
            "API para automação de compras industriais com IA multi-agente. "
            "Utiliza Google Gemini, RAG e ML para recomendações inteligentes."
        ),
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ====== CORS SEGURO ======
    allowed_origins = _get_allowed_origins()
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    
    LOGGER.info(f"🔒 CORS configurado para: {allowed_origins}")

    # ====== ROUTERS PRINCIPAIS ======
    from app.routers.dashboard_router import router as dashboard_router
    from app.routers.agent_router import router as agent_router
    from app.routers.ml_router import router as ml_router
    from app.routers.sales_router import router as sales_router
    from app.routers.tasks_router import router as tasks_router
    
    application.include_router(tasks_router)
    application.include_router(sales_router)
    application.include_router(dashboard_router)
    application.include_router(ml_router)
    application.include_router(agent_router)

    # ====== API ROUTERS (Frontend) ======
    from app.routers import (
        api_dashboard_router, 
        api_product_router, 
        api_agent_router, 
        api_order_router,
        api_chat_router, 
        api_supplier_router, 
        api_audit_router
    )
    
    application.include_router(api_dashboard_router.router)
    application.include_router(api_product_router.router)
    application.include_router(api_agent_router.router)
    application.include_router(api_order_router.router)
    application.include_router(api_chat_router.router)
    application.include_router(api_supplier_router.router)
    application.include_router(api_audit_router.router)
    
    # ====== RAG ROUTER ======
    from app.routers.rag_router import router as rag_router
    application.include_router(rag_router)

    # ====== AUTH ROUTER ======
    from app.routers.auth_router import router as auth_router
    application.include_router(auth_router)
    
    # ====== ADMIN ROUTER (Novo) ======
    from app.routers.admin_router import router as admin_router
    application.include_router(admin_router)

    # ====== EXCEPTION HANDLERS (Padronizados) ======
    
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handler padrão para exceções HTTP."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path)
            }
        )
    
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handler para erros de validação (422)."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": 422,
                "message": "Dados de entrada inválidos",
                "details": exc.errors(),
                "path": str(request.url.path)
            }
        )
    
    @application.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handler genérico para exceções não tratadas (500)."""
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

    # ====== HEALTH CHECK ======
    @application.get("/health", tags=["health"])
    async def healthcheck() -> Dict[str, Any]:
        """
        Health check simples para readiness probes.
        
        Para health check detalhado, use /admin/health
        """
        return {"status": "ok"}

    return application


# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

app: FastAPI = create_application()
