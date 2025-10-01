"""Service layer helpers for interacting with Celery tasks."""

from __future__ import annotations

from typing import Any, Dict, Optional

from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.tasks.debug_tasks import long_running_task
from app.tasks.ml_tasks import retrain_model_task


def trigger_long_running_task(duration_seconds: int = 5) -> AsyncResult:
    """Schedule the debug long running task and return the async result handle."""
    return long_running_task.delay(duration_seconds)


def trigger_retrain_model_task(produto_id: int, destinatario_email: Optional[str] = None) -> AsyncResult:
    """Schedule the ML retraining pipeline for the provided product."""

    return retrain_model_task.delay(produto_id, destinatario_email)


def get_task_status(task_id: str) -> Dict[str, Optional[Any]]:
    """Fetch the current state for a Celery task ID."""
    async_result = AsyncResult(task_id, app=celery_app)
    result: Optional[Any]
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
