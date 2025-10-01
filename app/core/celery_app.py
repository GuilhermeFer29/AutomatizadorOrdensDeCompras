"""Celery application factory and configuration."""

from __future__ import annotations

import os
from functools import lru_cache

from celery import Celery
from celery.schedules import crontab

DEFAULT_BROKER_URL = "redis://broker:6379/0"


def _build_scraping_schedule() -> crontab:
    cron_expression = os.getenv("SCRAPING_SCHEDULE_CRON", "0 */8 * * *")
    fields = cron_expression.split()
    if len(fields) != 5:
        return crontab(minute=0, hour="*/8")

    minute, hour, day_of_month, month_of_year, day_of_week = fields
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


@lru_cache(maxsize=1)
def create_celery_app() -> Celery:
    """Create and configure the Celery application instance."""
    broker_url = os.getenv("REDIS_URL", DEFAULT_BROKER_URL)
    backend_url = os.getenv("CELERY_RESULT_BACKEND", broker_url)

    celery_app = Celery(
        "automacao_inteligente_compras",
        broker=broker_url,
        backend=backend_url,
    )

    celery_app.conf.update(
        task_default_queue="default",
        task_routes={"app.tasks.*": {"queue": "default"}},
        result_expires=3600,
        timezone="UTC",
        worker_disable_rate_limits=True,
    )

    celery_app.conf.beat_schedule = {
        "scrape-products-periodically": {
            "task": "app.tasks.scraping.scrape_all_products",
            "schedule": _build_scraping_schedule(),
        }
    }

    celery_app.set_default()

    return celery_app


celery_app: Celery = create_celery_app()

# Import tasks to ensure they are registered with the Celery application.
import app.tasks.debug_tasks  # noqa: E402,F401
import app.tasks.ml_tasks  # noqa: E402,F401
import app.tasks.scraping_tasks  # noqa: E402,F401
