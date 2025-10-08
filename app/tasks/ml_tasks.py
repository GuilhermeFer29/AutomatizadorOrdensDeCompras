"""Tarefas Celery para treinar o modelo global LightGBM e exportar métricas."""

from __future__ import annotations

from typing import Any, Dict

import structlog
from celery import shared_task
from sqlmodel import Session

from app.core.database import engine
from app.ml.training import train_global_lgbm_model
from app.models.models import ModeloGlobal


LOGGER = structlog.get_logger(__name__)
@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.retrain_all_products_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def retrain_global_model_task(self) -> Dict[str, Any]:
    """Executa o treinamento global com LightGBM e retorna métricas."""

    LOGGER.info("ml.tasks.retrain_global.start")
    metrics = train_global_lgbm_model()

    with Session(engine) as session:
        registro = session.exec(
            ModeloGlobal.select().order_by(ModeloGlobal.treinado_em.desc())
        ).first()

    payload: Dict[str, Any] = {
        "status": "success",
        "metrics": metrics,
        "modelo_versao": registro.versao if registro else None,
    }

    LOGGER.info("ml.tasks.retrain_global.completed", **payload)
    return payload
