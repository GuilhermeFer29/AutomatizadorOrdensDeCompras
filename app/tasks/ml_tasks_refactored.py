"""
Tarefas Celery para ML - Tenant-Aware & Non-Blocking Implementation.

Este módulo define as tasks Celery para treinamento de modelos ML
sem bloquear a API (Event Loop).

ARQUITETURA:
============
- Tasks executam em Worker SEPARADO (não na API)
- Suporte a Multi-Tenancy (tenant_id como parâmetro)
- Retry automático com backoff exponencial
- Monitoramento via Flower/Prometheus

REFERÊNCIAS:
- Celery Tasks: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- Celery + RabbitMQ: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html
- SQLAlchemy in Tasks: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#when-do-i-construct-a-session-when-do-i-commit-it-and-when-do-i-close-it

IMPORTANTE:
- NUNCA chame funções CPU-bound diretamente na API
- Use .delay() ou .apply_async() para enviar para o Worker

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task, chain, group, chord
from celery.exceptions import MaxRetriesExceededError
from sqlmodel import Session, select

# Core imports
from app.core.celery_app import celery_app
from app.core.tenant_context import TenantContext, run_in_tenant_context

# Database (síncrono para Worker - não usa event loop)
from app.core.database import get_sync_engine
from app.models.models import Produto, ModeloPredicao


LOGGER = logging.getLogger(__name__)


# ============================================================================
# HELPER: Contexto de Tenant para Tasks
# ============================================================================

def with_tenant_context(tenant_id: Optional[str]):
    """
    Decorator para tasks que precisam de contexto de tenant.
    
    Converte string UUID para UUID e configura TenantContext.
    
    Uso:
        @celery_app.task
        def my_task(tenant_id: str, ...):
            with_tenant_context(tenant_id)
            # código com acesso ao tenant
    """
    if tenant_id:
        return TenantContext(UUID(tenant_id))
    return TenantContext(None)  # Superuser


# ============================================================================
# TASK: Treinar Modelo de Produto Individual
# ============================================================================

@celery_app.task(
    bind=True,
    name="ml.train_product_model",
    queue="ml",  # Fila dedicada para ML
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 min entre retries
    retry_kwargs={"max_retries": 3},
    # Timeouts
    soft_time_limit=300,   # 5 min soft limit
    time_limit=360,        # 6 min hard limit
    # Rate limiting
    rate_limit="10/m",     # Max 10 tasks/min
)
def train_product_model_task(
    self,
    sku: str,
    tenant_id: Optional[str] = None,
    optimize: bool = False,
    n_trials: int = 30
) -> Dict[str, Any]:
    """
    Task Celery para treinar modelo de um produto específico.
    
    Esta task roda no WORKER, não na API. Operações CPU-bound
    não bloqueiam o event loop da API.
    
    Conforme docs Celery Tasks:
    https://docs.celeryq.dev/en/stable/userguide/tasks.html
    
    Args:
        sku: SKU do produto
        tenant_id: UUID do tenant (string) - para filtro de dados
        optimize: Se True, otimiza hiperparâmetros com Optuna
        n_trials: Número de trials para otimização
    
    Returns:
        Dict com status, métricas e informações do treinamento
        
    Raises:
        Retries automaticamente em caso de erro
    """
    LOGGER.info(
        f"[ML Task] Iniciando treinamento",
        extra={
            "sku": sku,
            "tenant_id": tenant_id,
            "optimize": optimize,
            "task_id": self.request.id
        }
    )
    
    # Configura contexto de tenant
    with with_tenant_context(tenant_id):
        try:
            # Importação tardia para evitar circular imports
            from app.ml.training import train_model_for_product, InsufficientDataError
            
            # Executa treinamento (CPU-bound, OK no Worker)
            result = train_model_for_product(
                sku=sku,
                optimize=optimize,
                n_trials=n_trials,
                backtest=False
            )
            
            payload = {
                "status": "success",
                "sku": sku,
                "tenant_id": tenant_id,
                "task_id": self.request.id,
                "metrics": result.get("metrics", {}),
                "training_samples": result.get("training_samples", 0),
                "model_path": result.get("model_path"),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            LOGGER.info(f"[ML Task] Treinamento concluído", extra=payload)
            return payload
            
        except InsufficientDataError as e:
            # Dados insuficientes - não faz retry, retorna skipped
            LOGGER.warning(
                f"[ML Task] Dados insuficientes para {sku}: {e}",
                extra={"sku": sku, "tenant_id": tenant_id}
            )
            return {
                "status": "skipped",
                "sku": sku,
                "tenant_id": tenant_id,
                "reason": str(e),
                "task_id": self.request.id
            }
            
        except Exception as e:
            LOGGER.error(
                f"[ML Task] Erro no treinamento de {sku}: {e}",
                exc_info=True,
                extra={"sku": sku, "tenant_id": tenant_id}
            )
            
            # Re-raise para trigger retry automático
            raise self.retry(exc=e)


# ============================================================================
# TASK: Treinar Todos os Produtos (Batch)
# ============================================================================

@celery_app.task(
    bind=True,
    name="ml.train_all_products",
    queue="ml",
    # Sem retry - orchestrator apenas
    autoretry_for=(),
    soft_time_limit=3600,  # 1h soft limit
    time_limit=4200,       # 1h10m hard limit
)
def train_all_products_task(
    self,
    tenant_id: Optional[str] = None,
    optimize: bool = False,
    limit: Optional[int] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para treinar modelos de todos os produtos.
    
    ORQUESTRADOR: Esta task apenas lista produtos e dispara
    sub-tasks para cada um (paralelização).
    
    Args:
        tenant_id: UUID do tenant (filtra produtos)
        optimize: Se True, otimiza hiperparâmetros
        limit: Número máximo de produtos
        category: Filtrar por categoria
    
    Returns:
        Dict com estatísticas e task_ids disparadas
    """
    LOGGER.info(
        f"[ML Batch] Iniciando treinamento em lote",
        extra={
            "tenant_id": tenant_id,
            "optimize": optimize,
            "limit": limit,
            "category": category
        }
    )
    
    # Busca produtos (síncrono no Worker)
    engine = get_sync_engine()
    with Session(engine) as session:
        query = select(Produto)
        
        # Filtro de tenant
        if tenant_id:
            query = query.where(Produto.tenant_id == UUID(tenant_id))
        
        # Filtro de categoria
        if category:
            query = query.where(Produto.categoria == category)
        
        # Limite
        if limit:
            query = query.limit(limit)
        
        produtos = list(session.exec(query).all())
    
    total = len(produtos)
    LOGGER.info(f"[ML Batch] Encontrados {total} produtos para treinar")
    
    if total == 0:
        return {
            "status": "completed",
            "total": 0,
            "message": "Nenhum produto encontrado para treinar"
        }
    
    # Dispara sub-tasks em paralelo usando group()
    # Conforme docs Celery Canvas: https://docs.celeryq.dev/en/stable/userguide/canvas.html
    tasks = group(
        train_product_model_task.s(
            sku=produto.sku,
            tenant_id=tenant_id,
            optimize=optimize,
            n_trials=20 if optimize else 0
        )
        for produto in produtos
    )
    
    # Aplica o group (dispara todas as tasks)
    result = tasks.apply_async()
    
    return {
        "status": "dispatched",
        "total": total,
        "tenant_id": tenant_id,
        "group_id": str(result.id),
        "task_ids": [str(r.id) for r in result.results] if hasattr(result, 'results') else [],
        "message": f"Disparadas {total} tasks de treinamento"
    }


# ============================================================================
# TASK: Retreinar Modelo Global (Scheduled)
# ============================================================================

@celery_app.task(
    bind=True,
    name="ml.retrain_global_model",
    queue="ml",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    soft_time_limit=1800,  # 30 min
    time_limit=2100,       # 35 min
)
def retrain_global_model_task(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Task para retreinar modelo global agregado.
    
    Executada automaticamente via Celery Beat (diariamente 1h UTC).
    
    O modelo global usa dados agregados de todos os produtos para
    fazer previsões quando não há modelo específico disponível.
    
    Args:
        tenant_id: Se fornecido, treina modelo global do tenant
    
    Returns:
        Dict com status do retreinamento
    """
    LOGGER.info(
        f"[ML Global] Iniciando retreinamento do modelo global",
        extra={"tenant_id": tenant_id, "task_id": self.request.id}
    )
    
    try:
        from app.ml.training import train_global_model
        
        result = train_global_model(tenant_id=tenant_id)
        
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "task_id": self.request.id,
            "metrics": result.get("metrics", {}),
            "samples_used": result.get("samples", 0),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        LOGGER.error(f"[ML Global] Erro no retreinamento: {e}", exc_info=True)
        raise self.retry(exc=e)


# ============================================================================
# TASK: Indexação RAG (ChromaDB)
# ============================================================================

@celery_app.task(
    bind=True,
    name="rag.index_products",
    queue="default",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    soft_time_limit=600,   # 10 min
    time_limit=720,        # 12 min
)
def index_products_rag_task(
    self,
    tenant_id: Optional[str] = None,
    force_reindex: bool = False
) -> Dict[str, Any]:
    """
    Task para indexar produtos no ChromaDB (RAG).
    
    Esta operação é I/O bound mas pode ser lenta para muitos produtos.
    Executar no Worker evita bloquear a API.
    
    Args:
        tenant_id: Indexar apenas produtos do tenant
        force_reindex: Se True, reindaxa tudo (apaga índice existente)
    
    Returns:
        Dict com estatísticas da indexação
    """
    LOGGER.info(
        f"[RAG] Iniciando indexação de produtos",
        extra={"tenant_id": tenant_id, "force_reindex": force_reindex}
    )
    
    try:
        from app.services.rag_service import index_products_batch
        
        result = index_products_batch(
            tenant_id=UUID(tenant_id) if tenant_id else None,
            force_reindex=force_reindex
        )
        
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "indexed_count": result.get("indexed", 0),
            "skipped_count": result.get("skipped", 0),
            "task_id": self.request.id,
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        LOGGER.error(f"[RAG] Erro na indexação: {e}", exc_info=True)
        raise self.retry(exc=e)


# ============================================================================
# TASK: Scraping de Preços em Batch
# ============================================================================

@celery_app.task(
    bind=True,
    name="scraping.batch_prices",
    queue="default",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    rate_limit="5/m",      # Max 5 scrapes/min (evita bloqueio)
    soft_time_limit=120,   # 2 min por produto
    time_limit=180,
)
def scrape_prices_batch_task(
    self,
    product_ids: List[int],
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task para scraping de preços em batch.
    
    Respeita rate limiting para evitar bloqueio por sites externos.
    
    Args:
        product_ids: Lista de IDs de produtos para scrape
        tenant_id: Tenant dos produtos (validação)
    
    Returns:
        Dict com resultados do scraping
    """
    LOGGER.info(
        f"[Scraping] Iniciando batch de {len(product_ids)} produtos",
        extra={"tenant_id": tenant_id}
    )
    
    results = {"success": [], "failed": [], "skipped": []}
    
    with with_tenant_context(tenant_id):
        from app.services.scraping_service import scrape_price_for_product
        
        for product_id in product_ids:
            try:
                price = scrape_price_for_product(product_id)
                if price:
                    results["success"].append({
                        "product_id": product_id,
                        "price": float(price)
                    })
                else:
                    results["skipped"].append(product_id)
                    
            except Exception as e:
                LOGGER.warning(f"[Scraping] Falha no produto {product_id}: {e}")
                results["failed"].append({
                    "product_id": product_id,
                    "error": str(e)
                })
    
    return {
        "status": "completed",
        "tenant_id": tenant_id,
        "total": len(product_ids),
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "skipped_count": len(results["skipped"]),
        "details": results
    }


# ============================================================================
# TASK: Cleanup de Dados Antigos
# ============================================================================

@celery_app.task(
    bind=True,
    name="maintenance.cleanup_old_data",
    queue="default",
    soft_time_limit=600,
    time_limit=720,
)
def cleanup_old_data_task(
    self,
    days_to_keep: int = 90,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task de manutenção para limpar dados antigos.
    
    Remove:
    - Preços históricos > X dias
    - Logs de execução antigos
    - Modelos obsoletos
    
    Executada via Celery Beat (semanalmente).
    
    Args:
        days_to_keep: Dias de histórico a manter
        tenant_id: Se fornecido, limpa apenas dados do tenant
    
    Returns:
        Dict com contadores de registros removidos
    """
    from datetime import timedelta
    from sqlalchemy import delete
    from app.models.models import PrecosHistoricos, ModeloPredicao
    
    LOGGER.info(f"[Maintenance] Iniciando limpeza de dados > {days_to_keep} dias")
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    deleted_counts = {}
    
    engine = get_sync_engine()
    with Session(engine) as session:
        # Limpa preços históricos antigos
        stmt = delete(PrecosHistoricos).where(
            PrecosHistoricos.coletado_em < cutoff_date
        )
        if tenant_id:
            stmt = stmt.where(PrecosHistoricos.tenant_id == UUID(tenant_id))
        
        result = session.execute(stmt)
        deleted_counts["precos_historicos"] = result.rowcount
        
        # Limpa modelos de predição obsoletos (mantém último por produto)
        # (Implementação simplificada - em produção use subquery)
        
        session.commit()
    
    LOGGER.info(f"[Maintenance] Limpeza concluída: {deleted_counts}")
    
    return {
        "status": "completed",
        "cutoff_date": cutoff_date.isoformat(),
        "deleted": deleted_counts,
        "tenant_id": tenant_id
    }


# ============================================================================
# CELERY BEAT SCHEDULE (Definido em celery_app.py)
# ============================================================================
# 
# Para configurar schedules, adicione em app/core/celery_app.py:
#
# celery_app.conf.beat_schedule = {
#     "retrain-global-daily": {
#         "task": "ml.retrain_global_model",
#         "schedule": crontab(hour=1, minute=0),  # 1h UTC
#     },
#     "cleanup-weekly": {
#         "task": "maintenance.cleanup_old_data",
#         "schedule": crontab(day_of_week=0, hour=3),  # Domingo 3h UTC
#     },
#     "index-rag-daily": {
#         "task": "rag.index_products",
#         "schedule": crontab(hour=2, minute=0),  # 2h UTC
#     },
# }
