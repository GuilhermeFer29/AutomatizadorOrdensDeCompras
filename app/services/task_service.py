"""Service layer helpers for interacting with Celery tasks."""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.tasks.ml_tasks import train_all_products_task, train_product_model_task


def trigger_train_product_model_task(sku: str, optimize: bool = False) -> AsyncResult:
    """Agenda o treinamento de um modelo de produto específico."""
    return train_product_model_task.delay(sku, optimize)


def trigger_train_all_products_task(optimize: bool = False, limit: int = None) -> AsyncResult:
    """Agenda o treinamento de modelos para todos os produtos."""
    return train_all_products_task.delay(optimize, limit)


def get_task_status(task_id: str) -> dict[str, Any | None]:
    """Fetch the current state for a Celery task ID."""
    async_result = AsyncResult(task_id, app=celery_app)
    result: Any | None
    if async_result.successful():
        result = async_result.result
    elif async_result.failed():
        result = str(async_result.result)
    else:
        result = None

    return {
        "task_id": task_id,
        "state": async_result.state,
        "result": result,
    }
