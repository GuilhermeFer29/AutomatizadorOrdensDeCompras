"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import create_db_and_tables
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

    @application.on_event("startup")
    async def on_startup() -> None:  # noqa: D401 - simple startup hook
        create_db_and_tables()
        LOGGER.info("FastAPI application started successfully")

    @application.get("/health", tags=["health"])
    async def healthcheck() -> Dict[str, Any]:
        """Return a simple health indicator for readiness probes."""
        return {"status": "ok"}

    return application


app: FastAPI = create_application()
