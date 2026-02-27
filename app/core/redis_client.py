"""
Sync Redis client singleton para uso em operações leves (rate-limiting, state, etc.).

NOTA: Para operações async, use `app.services.redis_events.RedisEventManager`.
Este módulo fornece um client **sync** (redis-py) para contextos onde
async não é necessário (background tasks, rate limiting, sync state).

Autor: Sistema PMI | Data: 2026-02-27
"""

from __future__ import annotations

import logging
import os

import redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """
    Retorna uma instância singleton do Redis sync client.

    Lê configuração das variáveis de ambiente (REDIS_HOST, REDIS_PORT)
    ou usa defaults compatíveis com Docker Compose.

    Returns:
        redis.Redis | None — client conectado ou None se indisponível.
    """
    global _client

    if _client is not None:
        try:
            _client.ping()
            return _client
        except Exception:
            _client = None

    try:
        host = os.getenv("REDIS_HOST", "redis")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD")

        _client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            socket_timeout=5,
            socket_connect_timeout=5,
            decode_responses=True,
        )
        _client.ping()
        logger.debug("Redis sync client conectado em %s:%s/%s", host, port, db)
        return _client
    except Exception as exc:
        logger.warning("Redis indisponível (sync client): %s", exc)
        _client = None
        return None
