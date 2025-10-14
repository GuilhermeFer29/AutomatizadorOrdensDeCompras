"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import create_db_and_tables
from app.routers.dashboard_router import router as dashboard_router
from app.routers.agent_router import router as agent_router
from app.routers.ml_router import router as ml_router
from app.routers.sales_router import router as sales_router
from app.routers.tasks_router import router as tasks_router

load_dotenv()
LOGGER = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    application = FastAPI(
        title="Automação Inteligente de Ordens de Compra",
        description=(
            "API para monitoramento de tarefas Celery na plataforma preditiva de cadeia de suprimentos."
        ),
        version="0.1.0",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(tasks_router)
    application.include_router(sales_router)
    application.include_router(dashboard_router)
    application.include_router(ml_router)
    application.include_router(agent_router)

    # API Routers for Frontend
    from app.routers import api_dashboard_router, api_product_router, api_agent_router, api_order_router
    application.include_router(api_dashboard_router.router)
    application.include_router(api_product_router.router)
    application.include_router(api_agent_router.router)
    application.include_router(api_order_router.router)

    from app.routers import api_chat_router
    application.include_router(api_chat_router.router)

    # Adicionando a rota de fornecedores
    from app.routers.supplier_router import router as supplier_router
    application.include_router(supplier_router)
    
    # Rota de gerenciamento do RAG
    from app.routers.rag_router import router as rag_router
    application.include_router(rag_router)

    @application.on_event("startup")
    async def on_startup() -> None:  # noqa: D401 - simple startup hook
        create_db_and_tables()
        
        # ✅ Sincronização automática do RAG com banco de dados
        try:
            from app.services.rag_sync_service import initialize_rag_on_startup
            
            LOGGER.info("🔄 Iniciando sincronização automática do RAG...")
            result = initialize_rag_on_startup()
            
            if result["status"] == "success":
                LOGGER.info(f"✅ RAG sincronizado: {result['products_indexed']} produtos indexados")
            else:
                LOGGER.warning(f"⚠️ RAG não sincronizado: {result['message']}")
        except Exception as e:
            LOGGER.error(f"❌ Erro ao inicializar RAG: {e}")
            # Não bloqueia a inicialização da API se RAG falhar
        
        # ✅ Inicia listener do Redis para notificações em tempo real
        try:
            from app.services.redis_events import redis_events
            from app.services.websocket_manager import websocket_manager
            
            await redis_events.connect()
            
            # Handler que recebe mensagens do Redis e envia via WebSocket
            async def handle_redis_message(session_id: int, message_data: dict):
                LOGGER.info(f"📥 Redis → WebSocket: session_id={session_id}")
                await websocket_manager.send_message(session_id, message_data)
            
            # Inicia escuta em background
            await redis_events.start_listening(handle_redis_message)
            LOGGER.info("✅ Redis listener iniciado com sucesso")
        except Exception as e:
            LOGGER.warning(f"⚠️ Redis listener não iniciado: {e}")
        
        LOGGER.info("FastAPI application started successfully")
    
    @application.on_event("shutdown")
    async def on_shutdown() -> None:
        """Cleanup ao desligar."""
        try:
            from app.services.redis_events import redis_events
            await redis_events.disconnect()
            LOGGER.info("Redis listener desconectado")
        except Exception as e:
            LOGGER.warning(f"Erro ao desconectar Redis: {e}")

    @application.get("/health", tags=["health"])
    async def healthcheck() -> Dict[str, Any]:
        """Return a simple health indicator for readiness probes."""
        return {"status": "ok"}

    return application


app: FastAPI = create_application()
