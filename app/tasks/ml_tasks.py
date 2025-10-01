"""Celery tasks dedicated to training and notifying forecasting models."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from celery import shared_task
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import train_prophet_model
from app.models.models import ModeloPredicao, Produto
from app.services.email_service import TrainingReportData, send_training_report

LOGGER = logging.getLogger(__name__)


@shared_task(name="app.tasks.ml_tasks.retrain_model_task")
def retrain_model_task(produto_id: int, destinatario_email: Optional[str] = None) -> Dict[str, Any]:
    """Train the forecasting model for the given product and optionally send the report."""

    LOGGER.info("Iniciando tarefa de re-treino", extra={"produto_id": produto_id})

    pdf_path = train_prophet_model(produto_id=produto_id)

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        metadata = session.exec(
            select(ModeloPredicao)
            .where(ModeloPredicao.produto_id == produto_id)
            .order_by(ModeloPredicao.treinado_em.desc())
        ).first()

    metricas = metadata.metricas if metadata and metadata.metricas else {}
    report = TrainingReportData(
        produto_id=produto_id,
        pdf_path=pdf_path,
        metricas=metricas,
        to_email=destinatario_email,
        produto_nome=produto.nome if produto else None,
    )
    send_training_report(report)

    resultado = {
        "status": "success",
        "produto_id": produto_id,
        "pdf_path": pdf_path,
        "metricas": metricas,
        "produto_nome": produto.nome if produto else None,
    }

    LOGGER.info("Tarefa de re-treino finalizada", extra=resultado)
    return resultado
