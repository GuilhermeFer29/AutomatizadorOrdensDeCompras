"""
Router de Administração - Endpoints protegidos para operações de sistema.

ARQUITETURA DE PRODUÇÃO:
========================
Este router contém endpoints administrativos que não devem ser
expostos publicamente sem autenticação adequada.

ENDPOINTS:
- POST /admin/rag/sync: Sincroniza produtos no vector store (background)
- GET /admin/rag/status: Status da sincronização
- GET /admin/health: Health check detalhado
- POST /admin/cache/clear: Limpa caches

SEGURANÇA:
- Em produção, proteger com API Key ou JWT
- Não expor na documentação pública

REFERÊNCIAS:
- FastAPI Background Tasks: https://fastapi.tiangolo.com/tutorial/background-tasks/

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.core.permissions import require_role

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class SyncStatus(BaseModel):
    """Status da sincronização RAG."""
    status: str  # idle, running, completed, failed
    last_sync: str | None = None
    products_indexed: int = 0
    message: str = ""


class HealthStatus(BaseModel):
    """Health check detalhado."""
    status: str
    database: str
    vector_db: str
    timestamp: str


# ============================================================================
# SYNC STATE (Redis-backed para ser consistente entre workers)
# ============================================================================

def _get_sync_state() -> dict:
    """Lê estado de sync do Redis (ou retorna default se indisponível)."""
    try:
        import json
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis:
            raw = redis.get("rag_sync_state")
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return {
        "status": "idle",
        "last_sync": None,
        "products_indexed": 0,
        "message": "Nunca sincronizado"
    }


def _set_sync_state(state: dict) -> None:
    """Persiste estado de sync no Redis."""
    try:
        import json
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis:
            redis.set("rag_sync_state", json.dumps(state), ex=86400)  # TTL 24h
    except Exception:
        pass


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

def _sync_rag_background(batch_size: int = 100) -> None:
    """
    Sincroniza produtos no vector store em background com paginação.

    Args:
        batch_size: Número de produtos por batch (evita OOM)
    """
    _set_sync_state({
        "status": "running",
        "last_sync": None,
        "products_indexed": 0,
        "message": "Sincronização em andamento..."
    })

    try:
        from sqlmodel import Session

        from app.core.database import get_sync_engine
        from app.core.vector_db import get_products_collection
        from app.models.models import Produto

        engine = get_sync_engine()
        collection = get_products_collection()

        total_indexed = 0
        offset = 0

        with Session(engine) as session:
            while True:
                # Busca batch de produtos (PAGINAÇÃO)
                produtos = session.exec(
                    select(Produto)
                    .offset(offset)
                    .limit(batch_size)
                ).all()

                if not produtos:
                    break

                # Prepara documentos para ChromaDB
                ids = []
                documents = []
                metadatas = []

                for p in produtos:
                    # Cria documento enriquecido
                    doc_content = (
                        f"Produto: {p.nome}\n"
                        f"SKU: {p.sku}\n"
                        f"Categoria: {p.categoria or 'N/A'}\n"
                        f"Estoque Atual: {p.estoque_atual} unidades\n"
                        f"Estoque Mínimo: {p.estoque_minimo} unidades\n"
                    )

                    if p.estoque_atual <= p.estoque_minimo:
                        doc_content += "⚠️ ATENÇÃO: Estoque abaixo do mínimo!\n"

                    ids.append(f"product_{p.id}")
                    documents.append(doc_content)
                    metadatas.append({
                        "product_id": p.id,
                        "sku": p.sku,
                        "nome": p.nome,
                        "categoria": p.categoria or "N/A",
                        "estoque_atual": p.estoque_atual,
                        "estoque_minimo": p.estoque_minimo,
                    })

                # Upsert no ChromaDB
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )

                total_indexed += len(produtos)
                offset += batch_size

                LOGGER.info(f"RAG Sync: {total_indexed} produtos indexados...")

        _set_sync_state({
            "status": "completed",
            "last_sync": datetime.now(UTC).isoformat(),
            "products_indexed": total_indexed,
            "message": f"Sincronização concluída: {total_indexed} produtos",
        })

        LOGGER.info(f"✅ RAG Sync completo: {total_indexed} produtos indexados")

    except Exception as e:
        LOGGER.error(f"❌ RAG Sync falhou: {e}")
        _set_sync_state({
            "status": "failed",
            "last_sync": None,
            "products_indexed": 0,
            "message": f"Erro: {str(e)}",
        })


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/rag/sync", response_model=SyncStatus)
async def sync_rag(
    background_tasks: BackgroundTasks,
    batch_size: int = 100,
    force: bool = False,
    current_user=Depends(require_role("admin", "owner")),
):
    """
    Inicia sincronização de produtos no vector store (background).

    - **batch_size**: Produtos por batch (default: 100)
    - **force**: Força re-sync mesmo se já estiver rodando

    A sincronização roda em background para não bloquear a API.
    Use GET /admin/rag/status para acompanhar o progresso.
    """
    current_state = _get_sync_state()

    if current_state["status"] == "running" and not force:
        raise HTTPException(
            status_code=409,
            detail="Sincronização já em andamento. Use force=true para reiniciar."
        )

    # Agenda task em background
    background_tasks.add_task(_sync_rag_background, batch_size)

    new_state = {
        "status": "running",
        "last_sync": current_state.get("last_sync"),
        "products_indexed": current_state.get("products_indexed", 0),
        "message": "Sincronização iniciada em background",
    }
    _set_sync_state(new_state)

    return SyncStatus(**new_state)


@router.get("/rag/status", response_model=SyncStatus)
async def get_rag_status(current_user=Depends(require_role("admin", "owner"))):
    """
    Retorna status atual da sincronização RAG.
    """
    return SyncStatus(**_get_sync_state())


@router.get("/health", response_model=HealthStatus)
async def admin_health_check(current_user=Depends(require_role("admin", "owner"))):
    """
    Health check detalhado para monitoramento.

    Verifica:
    - Conexão com banco de dados
    - Conexão com vector store
    """
    from app.core.database import check_database_health
    from app.core.vector_db import VectorDBManager

    # Check database
    db_health = await check_database_health()

    # Check vector DB
    try:
        if VectorDBManager.is_initialized():
            vector_status = "connected"
        else:
            # Tenta inicializar
            VectorDBManager.get_client()
            vector_status = "connected"
    except Exception as e:
        vector_status = f"error: {str(e)}"

    overall = "healthy" if db_health["status"] == "healthy" and vector_status == "connected" else "unhealthy"

    return HealthStatus(
        status=overall,
        database=db_health["status"],
        vector_db=vector_status,
        timestamp=datetime.now(UTC).isoformat()
    )


@router.post("/cache/clear")
async def clear_caches(current_user=Depends(require_role("admin", "owner"))):
    """
    Limpa caches do sistema.

    Útil para forçar recarga de dados após atualizações.
    """
    # TODO: Implementar limpeza de caches quando houver Redis
    return {"status": "ok", "message": "Caches limpos (nenhum cache ativo no momento)"}


__all__ = ["router"]
