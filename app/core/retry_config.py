"""
Configuração de retry para lidar com rate limits da API Gemini.

Este módulo fornece decorators e configurações para retry automático
quando a API retorna erro 429 (Too Many Requests).
"""

import functools
import time
from collections.abc import Callable
from typing import Any

import structlog

LOGGER = structlog.get_logger(__name__)


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 5.0):
    """
    Decorator para retry automático em caso de rate limit (429).

    Implementa exponential backoff:
    - Tentativa 1: espera base_delay segundos
    - Tentativa 2: espera base_delay * 2 segundos
    - Tentativa 3: espera base_delay * 4 segundos

    Args:
        max_retries: Número máximo de tentativas (padrão: 3)
        base_delay: Delay base em segundos (padrão: 5.0)

    Usage:
        @retry_on_rate_limit(max_retries=3, base_delay=10.0)
        def my_function():
            # código que pode retornar 429
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    # Verifica se é erro de rate limit (429)
                    error_str = str(e)
                    is_rate_limit = (
                        "429" in error_str or
                        "Too Many Requests" in error_str or
                        "RESOURCE_EXHAUSTED" in error_str or
                        "quota" in error_str.lower()
                    )

                    if not is_rate_limit:
                        # Se não é rate limit, propaga imediatamente
                        raise

                    last_exception = e

                    # Se é a última tentativa, propaga o erro
                    if attempt == max_retries - 1:
                        LOGGER.error(
                            "Rate limit retry esgotado",
                            function=func.__name__,
                            attempts=max_retries,
                            error=str(e)
                        )
                        raise

                    # Calcula delay com exponential backoff
                    delay = base_delay * (2 ** attempt)

                    LOGGER.warning(
                        "Rate limit detectado - aguardando retry",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay_seconds=delay
                    )

                    time.sleep(delay)

            # Fallback (não deve chegar aqui, mas por segurança)
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def get_retry_delay_from_error(error: Exception) -> float:
    """
    Extrai o tempo de retry recomendado pelo erro da API.

    O Gemini API retorna no erro quanto tempo aguardar:
    'retryDelay': '22s' ou similar.

    Args:
        error: Exception retornada pela API

    Returns:
        Segundos para aguardar (default: 30.0 se não encontrar)
    """
    error_str = str(error)

    # Tenta extrair retryDelay da mensagem de erro
    import re
    match = re.search(r"'retryDelay':\s*'(\d+)s'", error_str)

    if match:
        delay = float(match.group(1))
        LOGGER.info(f"API sugeriu retry em {delay}s")
        return delay

    # Se não encontrou, usa default conservador
    return 30.0


__all__ = [
    "retry_on_rate_limit",
    "get_retry_delay_from_error",
]
