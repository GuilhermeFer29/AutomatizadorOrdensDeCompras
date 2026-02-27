"""
Celery Application Factory - RabbitMQ Edition.

ARQUITETURA SaaS:
=================
- Broker: RabbitMQ (persistência, garantias de entrega)
- Result Backend: Redis (rápido, temporário)
- Quorum Queues: Para alta disponibilidade

REFERÊNCIAS:
- Celery RabbitMQ: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html
- Celery Config: https://docs.celeryq.dev/en/stable/userguide/configuration.html

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import os
from functools import lru_cache

from celery import Celery
from celery.schedules import crontab

# ============================================================================
# CONFIGURAÇÃO DE BROKERS
# ============================================================================

def _get_broker_url() -> str:
    """
    Retorna URL do RabbitMQ.

    Formato: amqp://user:password@host:port/vhost
    """
    # Tenta variável específica do Celery primeiro
    broker_url = os.getenv("CELERY_BROKER_URL")
    if broker_url:
        return broker_url

    # Constrói a partir das variáveis do RabbitMQ
    user = os.getenv("RABBITMQ_DEFAULT_USER", "pmi")
    password = os.getenv("RABBITMQ_DEFAULT_PASS", "pmi_secret")
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = os.getenv("RABBITMQ_PORT", "5672")
    vhost = os.getenv("RABBITMQ_DEFAULT_VHOST", "pmi")

    return f"amqp://{user}:{password}@{host}:{port}/{vhost}"


def _get_result_backend() -> str:
    """
    Retorna URL do Redis para result backend.
    """
    return os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")


# ============================================================================
# CELERY APP FACTORY
# ============================================================================

@lru_cache(maxsize=1)
def create_celery_app() -> Celery:
    """
    Cria e configura a aplicação Celery.

    Configuração otimizada para produção:
    - RabbitMQ como broker (persistent, reliable)
    - Redis como result backend (fast, temporary)
    - Prefetch multiplier baixo para distribuição justa
    - Acknowledgment tardio para retry em caso de crash
    """
    broker_url = _get_broker_url()
    backend_url = _get_result_backend()

    LOGGER = __import__('logging').getLogger(__name__)
    LOGGER.info("Celery Broker: %s", broker_url.split('@')[-1] if '@' in broker_url else broker_url)
    LOGGER.info("Result Backend: %s", backend_url)

    celery_app = Celery(
        "pmi_worker",
        broker=broker_url,
        backend=backend_url,
        broker_connection_retry_on_startup=True,
    )

    celery_app.conf.update(
        # Queue Configuration with DLQ (Dead Letter Queue)
        task_default_queue="default",
        task_queues={
            "default": {
                "exchange": "default",
                "routing_key": "default",
                "queue_arguments": {
                    "x-dead-letter-exchange": "dlx",
                    "x-dead-letter-routing-key": "dlq.default",
                },
            },
            "agents": {
                "exchange": "agents",
                "routing_key": "agents.#",
                "queue_arguments": {
                    "x-dead-letter-exchange": "dlx",
                    "x-dead-letter-routing-key": "dlq.agents",
                },
            },
            "ml": {
                "exchange": "ml",
                "routing_key": "ml.#",
                "queue_arguments": {
                    "x-dead-letter-exchange": "dlx",
                    "x-dead-letter-routing-key": "dlq.ml",
                },
            },
            "dlq": {
                "exchange": "dlx",
                "routing_key": "dlq.#",
            },
        },
        task_routes={
            "app.tasks.agent_tasks.*": {"queue": "agents"},
            "app.tasks.ml_tasks.*": {"queue": "ml"},
        },

        # Retry Policy (exponential backoff)
        task_default_retry_delay=60,      # 1 min initial
        task_max_retries=5,               # Max 5 retries

        # Performance & Reliability
        worker_prefetch_multiplier=1,  # Distribui tarefas de forma justa
        task_acks_late=True,           # ACK após execução (retry em crash)
        task_reject_on_worker_lost=True,

        # RabbitMQ: usar QoS per-consumer em vez de global (deprecated)
        broker_transport_options={
            "global_qos": False,
        },

        # Timeouts
        task_soft_time_limit=300,      # 5 min soft limit
        task_time_limit=600,           # 10 min hard limit
        result_expires=3600,           # Results expiram em 1 hora

        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",

        # Timezone
        timezone="America/Sao_Paulo",
        enable_utc=True,

        # Worker
        worker_disable_rate_limits=True,
        worker_send_task_events=True,  # Para monitoring
        task_send_sent_event=True,
    )

    # ==========================================================================
    # BEAT SCHEDULE (Tarefas Agendadas)
    # ==========================================================================
    celery_app.conf.beat_schedule = {
        # Retreinamento de modelo global diariamente
        'retrain-global-model-daily': {
            'task': 'app.tasks.ml_tasks.retrain_global_model_task',
            'schedule': crontab(hour=1, minute=0),  # 1h da manhã
            'options': {'queue': 'ml'},
        },
        # TODO: Implementar maintenance_tasks module
        # 'cleanup-old-results-weekly': {
        #     'task': 'app.tasks.maintenance_tasks.cleanup_old_results',
        #     'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),
        #     'options': {'queue': 'default'},
        # },
    }

    celery_app.set_default()

    return celery_app


# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

celery_app: Celery = create_celery_app()

# Import tasks to ensure they are registered
import app.tasks.agent_tasks  # noqa: E402,F401
import app.tasks.ml_tasks  # noqa: E402,F401
