"""Tarefas Celery para treinar modelos ML por produto.

ARQUITETURA NOVA (2025-10-16):
===============================
✅ Tasks para treinamento individual por SKU
✅ Tasks para treinamento em lote
✅ Integração com novo sistema de model_manager
"""

from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone

import structlog
from celery import shared_task
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import train_model_for_product, InsufficientDataError
from app.models.models import Produto, ModeloGlobal


LOGGER = structlog.get_logger(__name__)


@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.train_product_model_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def train_product_model_task(self, sku: str, optimize: bool = False) -> Dict[str, Any]:
    """
    Task Celery para treinar modelo de um produto específico.
    
    Args:
        sku: SKU do produto
        optimize: Se True, otimiza hiperparâmetros com Optuna
    
    Returns:
        Dicionário com status e métricas
    """
    LOGGER.info(f"ml.tasks.train_product.start", sku=sku, optimize=optimize)
    
    try:
        result = train_model_for_product(sku=sku, optimize=optimize, n_trials=30)
        
        payload = {
            "status": "success",
            "sku": sku,
            "metrics": result["metrics"],
            "training_samples": result["training_samples"],
        }
        
        LOGGER.info("ml.tasks.train_product.completed", **payload)
        return payload
    
    except InsufficientDataError as e:
        LOGGER.warning(f"ml.tasks.train_product.insufficient_data", sku=sku, error=str(e))
        return {
            "status": "skipped",
            "sku": sku,
            "reason": str(e),
        }
    
    except Exception as e:
        LOGGER.error(f"ml.tasks.train_product.failed", sku=sku, error=str(e), exc_info=True)
        raise


@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.train_all_products_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def train_all_products_task(self, optimize: bool = False, limit: int = None) -> Dict[str, Any]:
    """
    Task Celery para treinar modelos de todos os produtos.
    
    Args:
        optimize: Se True, otimiza hiperparâmetros
        limit: Número máximo de produtos (None = todos)
    
    Returns:
        Dicionário com estatísticas do treinamento
    """
    LOGGER.info("ml.tasks.train_all.start", optimize=optimize, limit=limit)
    
    # Buscar todos os produtos
    with Session(engine) as session:
        query = select(Produto)
        if limit:
            query = query.limit(limit)
        produtos = list(session.exec(query).all())
    
    total = len(produtos)
    results = {"success": [], "skipped": [], "failed": []}
    
    for idx, produto in enumerate(produtos, 1):
        LOGGER.info(f"ml.tasks.train_all.progress", current=idx, total=total, sku=produto.sku)
        
        try:
            result = train_model_for_product(
                sku=produto.sku,
                optimize=optimize,
                n_trials=20 if optimize else 0,
            )
            results["success"].append(produto.sku)
        
        except InsufficientDataError:
            results["skipped"].append(produto.sku)
        
        except Exception as e:
            LOGGER.error(f"ml.tasks.train_all.product_failed", sku=produto.sku, error=str(e))
            results["failed"].append(produto.sku)
    
    payload = {
        "status": "completed",
        "total": total,
        "success_count": len(results["success"]),
        "skipped_count": len(results["skipped"]),
        "failed_count": len(results["failed"]),
    }
    
    LOGGER.info("ml.tasks.train_all.completed", **payload)
    return payload


@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.retrain_global_model_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 1},
)
def retrain_global_model_task(self) -> Dict[str, Any]:
    """
    Task Celery para retreinar o modelo global agregado diariamente.
    
    Executada automaticamente via Celery Beat (1h da manhã UTC).
    
    Returns:
        Dicionário com status do retreinamento
    """
    LOGGER.info("ml.tasks.retrain_global.start")
    
    try:
        # Treinar todos os produtos para gerar dados para o modelo global
        with Session(engine) as session:
            query = select(Produto)
            produtos = list(session.exec(query).all())
        
        total = len(produtos)
        success_count = 0
        
        for idx, produto in enumerate(produtos, 1):
            LOGGER.info(f"ml.tasks.retrain_global.progress", current=idx, total=total, sku=produto.sku)
            
            try:
                train_model_for_product(sku=produto.sku, optimize=False, n_trials=0)
                success_count += 1
            except InsufficientDataError:
                LOGGER.warning(f"ml.tasks.retrain_global.insufficient_data", sku=produto.sku)
            except Exception as e:
                LOGGER.error(f"ml.tasks.retrain_global.product_failed", sku=produto.sku, error=str(e))
        
        # Registrar retreinamento no banco de dados
        with Session(engine) as session:
            global_model = ModeloGlobal(
                modelo_tipo="LightGBM_Global",
                versao="1.0",
                holdout_dias=7,
                caminho_modelo="models/global_model.pkl",
                caminho_relatorio="reports/global_model_report.html",
                metricas={
                    "produtos_treinados": success_count,
                    "total_produtos": total,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                treinado_em=datetime.now(timezone.utc),
            )
            session.add(global_model)
            session.commit()
        
        payload = {
            "status": "success",
            "total_produtos": total,
            "produtos_treinados": success_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        LOGGER.info("ml.tasks.retrain_global.completed", **payload)
        return payload
    
    except Exception as e:
        LOGGER.error("ml.tasks.retrain_global.failed", error=str(e), exc_info=True)
        raise
