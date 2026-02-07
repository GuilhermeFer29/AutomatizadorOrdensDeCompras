"""
Cache System com Redis usando fastapi-cache2.

ARQUITETURA SaaS:
=================
- Backend: Redis (db=1 para cache, db=0 para Celery results)
- TTL padrão: 5 minutos
- Invalidação automática em mutações

REFERÊNCIAS:
- fastapi-cache2: https://github.com/long2ice/fastapi-cache

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable

from fastapi import Request, Response
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache

LOGGER = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

CACHE_EXPIRE_SECONDS = int(os.getenv("CACHE_EXPIRE_SECONDS", "300"))  # 5 min
CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://redis:6379/1")


# ============================================================================
# KEY BUILDER CUSTOMIZADO (Com Tenant)
# ============================================================================

def tenant_aware_key_builder(
    func: Callable,
    namespace: str = "",
    request: Request | None = None,
    response: Response | None = None,
    args: tuple = (),
    kwargs: dict | None = None,
) -> str:
    """
    Gera chave de cache incluindo tenant_id para isolamento.

    Formato: {namespace}:{tenant_id}:{func_name}:{params_hash}
    """
    if kwargs is None:
        kwargs = {}
    from app.core.tenant import get_current_tenant_id

    # Obtém tenant da request atual
    tenant_id = get_current_tenant_id()
    tenant_str = str(tenant_id) if tenant_id else "global"

    # Hash dos parâmetros
    params = f"{args}:{kwargs}"
    params_hash = hashlib.sha256(params.encode()).hexdigest()[:8]

    # Monta chave
    prefix = namespace or "cache"
    func_name = func.__name__

    return f"{prefix}:{tenant_str}:{func_name}:{params_hash}"


# ============================================================================
# INICIALIZAÇÃO
# ============================================================================

async def init_cache() -> None:
    """
    Inicializa o cache Redis durante startup da aplicação.

    Chamado no lifespan do FastAPI.
    """
    try:
        from redis import asyncio as aioredis

        redis = aioredis.from_url(
            CACHE_REDIS_URL,
            encoding="utf8",
            decode_responses=True
        )

        FastAPICache.init(
            RedisBackend(redis),
            prefix="pmi-cache",
            key_builder=tenant_aware_key_builder
        )

        LOGGER.info(f"✅ Cache Redis inicializado: {CACHE_REDIS_URL}")

    except Exception as e:
        LOGGER.warning(f"⚠️ Cache Redis não disponível: {e}")


# ============================================================================
# DECORADORES DE CACHE
# ============================================================================

def cache_response(expire: int = CACHE_EXPIRE_SECONDS, namespace: str = ""):
    """
    Decorador para cachear resposta de endpoint.

    Args:
        expire: TTL em segundos (default: 300)
        namespace: Prefixo opcional para a chave

    Uso:
        @app.get("/products")
        @cache_response(expire=60, namespace="products")
        async def get_products():
            return await heavy_db_query()
    """
    return cache(
        expire=expire,
        namespace=namespace,
        key_builder=tenant_aware_key_builder
    )


# ============================================================================
# INVALIDAÇÃO DE CACHE
# ============================================================================

async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalida todas as chaves que correspondem ao padrão.

    Args:
        pattern: Padrão glob (ex: "products:*")

    Returns:
        Número de chaves removidas
    """
    try:
        from redis import asyncio as aioredis

        redis = aioredis.from_url(CACHE_REDIS_URL)

        # Busca chaves que correspondem ao padrão
        keys = []
        async for key in redis.scan_iter(f"pmi-cache:{pattern}"):
            keys.append(key)

        if keys:
            count = await redis.delete(*keys)
            LOGGER.info(f"🗑️ Cache invalidado: {count} chaves removidas (pattern: {pattern})")
            return count

        return 0

    except Exception as e:
        LOGGER.warning(f"Erro ao invalidar cache: {e}")
        return 0


async def invalidate_tenant_cache(tenant_id: str, namespace: str = "*") -> int:
    """
    Invalida todo o cache de um tenant específico.

    Args:
        tenant_id: UUID do tenant
        namespace: Namespace específico ou * para todos

    Returns:
        Número de chaves removidas
    """
    pattern = f"{namespace}:{tenant_id}:*"
    return await invalidate_cache_pattern(pattern)


async def invalidate_dashboard_cache() -> int:
    """
    Invalida cache do dashboard.

    Chamado automaticamente após criar/atualizar:
    - Ordens de compra
    - Produtos
    - Vendas
    """
    from app.core.tenant import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if tenant_id:
        return await invalidate_cache_pattern(f"dashboard:{tenant_id}:*")
    return await invalidate_cache_pattern("dashboard:*")


async def invalidate_products_cache() -> int:
    """Invalida cache de produtos."""
    from app.core.tenant import get_current_tenant_id

    tenant_id = get_current_tenant_id()
    if tenant_id:
        return await invalidate_cache_pattern(f"products:{tenant_id}:*")
    return await invalidate_cache_pattern("products:*")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "init_cache",
    "cache_response",
    "invalidate_cache_pattern",
    "invalidate_tenant_cache",
    "invalidate_dashboard_cache",
    "invalidate_products_cache",
    "CACHE_EXPIRE_SECONDS",
]
