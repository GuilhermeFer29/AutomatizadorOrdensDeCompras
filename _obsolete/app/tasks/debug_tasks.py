"""Debug and smoke-test Celery tasks."""

from __future__ import annotations

import time
from typing import Dict

from celery.app.task import Task
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app

LOGGER = get_task_logger(__name__)


@celery_app.task(name="app.tasks.debug.long_running_task", bind=True)
def long_running_task(self: Task, duration_seconds: int = 5) -> Dict[str, int]:
    """Execute a simple wait task to validate worker execution."""
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")

    LOGGER.info("[%s] Starting debug task for %s seconds", self.request.id, duration_seconds)
    time.sleep(duration_seconds)
    result: Dict[str, int] = {"duration_seconds": duration_seconds}
    LOGGER.info("[%s] Completed debug task: %s", self.request.id, result)
    return result
