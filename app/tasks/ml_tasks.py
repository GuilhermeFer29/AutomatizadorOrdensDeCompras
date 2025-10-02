"""Celery tasks responsible for retraining Prophet models and dispatching reports."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import structlog
from celery import shared_task
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import BulkTrainingResult, train_all_products, train_model
from app.models.models import ModeloPredicao, Produto
from app.services.email_service import send_bulk_training_report, send_training_report

LOGGER = structlog.get_logger(__name__)
DEFAULT_RECIPIENT = os.getenv("SMTP_DEFAULT_RECIPIENT", "").strip()


@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.retrain_model_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def retrain_model_task(
    self, produto_id: int, destinatario_email: Optional[str] = None
) -> Dict[str, Any]:
    """Trigger Prophet retraining for the product and distribute the PDF report."""

    LOGGER.info("ml.tasks.retrain_model.start", produto_id=produto_id)

    pdf_path = train_model(produto_id=produto_id)

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        metadata = session.exec(
            select(ModeloPredicao)
            .where(ModeloPredicao.produto_id == produto_id)
            .order_by(ModeloPredicao.treinado_em.desc())
        ).first()

    produto_nome = produto.nome if produto else f"ID {produto_id}"
    metricas_raw = metadata.metricas if metadata and metadata.metricas else {}
    metricas = {chave: float(valor) for chave, valor in metricas_raw.items()}

    recipient = destinatario_email or DEFAULT_RECIPIENT
    send_training_report(to_email=recipient, produto_id=produto_id, pdf_path=pdf_path)

    resultado: Dict[str, Any] = {
        "status": "success",
        "produto_id": produto_id,
        "produto_nome": produto_nome,
        "pdf_path": pdf_path,
        "metricas": metricas,
    }

    LOGGER.info("ml.tasks.retrain_model.completed", **resultado)
    return resultado


@shared_task(
    bind=True,
    name="app.tasks.ml_tasks.retrain_all_products_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def retrain_all_products_task(
    self, destinatario_email: Optional[str] = None
) -> Dict[str, Any]:
    """Trigger the consolidated Prophet retraining flow for the entire catalogue."""

    LOGGER.info("ml.tasks.retrain_all.start")

    result: BulkTrainingResult = train_all_products()

    recipient = destinatario_email or DEFAULT_RECIPIENT
    send_bulk_training_report(
        to_email=recipient,
        pdf_path=result.pdf_path,
        total_treinados=len(result.trained_products),
        total_ignorados=len(result.skipped),
    )

    skipped_payload = [
        {
            "produto_id": item.produto_id,
            "produto_nome": item.produto_nome,
            "motivo": item.reason,
        }
        for item in result.skipped
    ]

    payload: Dict[str, Any] = {
        "status": "success",
        "pdf_path": result.pdf_path,
        "trained_products": result.trained_products,
        "skipped": skipped_payload,
    }

    LOGGER.info("ml.tasks.retrain_all.completed", **payload)
    return payload
