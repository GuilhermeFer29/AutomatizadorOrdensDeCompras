"""
Gemini Model Fallback Manager - Gerenciamento automático de fallback entre modelos.

Este módulo implementa um sistema de fallback que:
1. Tenta o modelo primário (gemini-2.5-flash)
2. Em caso de erro 429 (rate limit), tenta modelos alternativos
3. Usa retry com exponential backoff
4. Faz log de todas as trocas de modelo

MODELOS NA CHAIN DE FALLBACK (em ordem de prioridade):
======================================================
1. gemini-2.5-flash   - Principal (mais novo, rápido)
2. gemini-2.0-flash   - Flash estável 2.0
3. gemini-1.5-flash   - Flash legacy 1.5
4. gemini-1.5-pro     - Pro model (mais quota, mais lento)

Uso:
    from app.agents.gemini_fallback import get_model_with_fallback, run_with_fallback

    # Obter modelo com fallback automático
    model = get_model_with_fallback(temperature=0.3)

    # Executar função com retry e fallback
    result = run_with_fallback(agent.run, "Sua mensagem aqui")
"""

import logging
import os
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from agno.models.google import Gemini

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURAÇÃO DA CHAIN DE FALLBACK
# ============================================================================

# Modelos em ordem de preferência (modelos válidos do Gemini)
# Nota: Os modelos devem existir na API - verificar em https://ai.google.dev/gemini-api/docs/models/gemini
MODEL_FALLBACK_CHAIN = [
    "gemini-2.5-flash",        # Primary: Newest flash model
    "gemini-2.5-flash-lite",   # Secondary: Lite version
    "gemini-3-flash",          # Tertiary: Next gen flash
]

# Configurações de retry
MAX_RETRIES_PER_MODEL = 2
INITIAL_BACKOFF_SECONDS = 1
BACKOFF_MULTIPLIER = 2
MAX_BACKOFF_SECONDS = 8


# ============================================================================
# GERENCIADOR DE FALLBACK
# ============================================================================

class GeminiFallbackManager:
    """
    Gerencia fallback automático entre modelos Gemini quando ocorrem erros de rate limit.

    Mantém estado do modelo atual e histórico de erros para decisões inteligentes.
    """

    _instance = None  # Singleton para manter estado global

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model_chain = MODEL_FALLBACK_CHAIN.copy()
        self.current_index = 0
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.last_switch_time = 0
        self.error_counts = {model: 0 for model in self.model_chain}
        self._initialized = True

        logger.info(f"🔄 GeminiFallbackManager inicializado com {len(self.model_chain)} modelos")

    @property
    def current_model_id(self) -> str:
        """Retorna o ID do modelo atual."""
        return self.model_chain[self.current_index]

    def get_model(self, temperature: float = 0.3) -> Gemini:
        """
        Retorna instância do modelo atual na chain de fallback.

        Args:
            temperature: Temperatura para o modelo (0.0 = determinístico, 1.0 = criativo)

        Returns:
            Gemini: Instância configurada do modelo atual
        """
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY não configurada")

        model_id = self.current_model_id
        logger.info(f"🤖 Usando modelo: {model_id} (index {self.current_index}/{len(self.model_chain)-1})")

        return Gemini(
            id=model_id,
            api_key=self.api_key,
            temperature=temperature,
        )

    def switch_to_next_model(self) -> bool:
        """
        Alterna para o próximo modelo na chain de fallback.

        Returns:
            bool: True se conseguiu alternar, False se não há mais modelos
        """
        if self.current_index >= len(self.model_chain) - 1:
            logger.error("❌ Todos os modelos na chain de fallback esgotaram quota!")
            return False

        old_model = self.current_model_id
        self.current_index += 1
        new_model = self.current_model_id
        self.last_switch_time = time.time()

        logger.warning(f"⚠️ Fallback: {old_model} -> {new_model} (rate limit)")
        print(f"⚠️ Modelo {old_model} com rate limit. Alternando para {new_model}")

        return True

    def reset_to_primary(self) -> None:
        """Reseta para o modelo primário (usar após período de cooldown)."""
        if self.current_index > 0:
            old_model = self.current_model_id
            self.current_index = 0
            logger.info(f"🔄 Resetando para modelo primário: {old_model} -> {self.current_model_id}")

    def should_try_primary(self) -> bool:
        """
        Verifica se deve tentar voltar ao modelo primário.
        Retorna True se passou tempo suficiente desde o último fallback.
        """
        # Se já está no primário, não precisa
        if self.current_index == 0:
            return False

        # Cooldown de 5 minutos antes de tentar primário novamente
        cooldown_seconds = 300
        elapsed = time.time() - self.last_switch_time

        if elapsed > cooldown_seconds:
            logger.info(f"⏰ Cooldown de {cooldown_seconds}s passou. Tentando modelo primário...")
            return True

        return False

    def record_error(self, model_id: str) -> None:
        """Registra erro para um modelo específico."""
        if model_id in self.error_counts:
            self.error_counts[model_id] += 1
            logger.debug(f"📊 Erros em {model_id}: {self.error_counts[model_id]}")


# ============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# ============================================================================

# Instância global do gerenciador
_fallback_manager: GeminiFallbackManager | None = None


def get_fallback_manager() -> GeminiFallbackManager:
    """Retorna a instância singleton do gerenciador de fallback."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = GeminiFallbackManager()
    return _fallback_manager


def get_model_with_fallback(temperature: float = 0.3) -> Gemini:
    """
    Retorna modelo Gemini atual da chain de fallback.

    Esta função é o ponto de entrada principal para obter um modelo.
    O modelo retornado depende do estado atual da chain de fallback.

    Args:
        temperature: Temperatura do modelo (padrão: 0.3)

    Returns:
        Gemini: Instância do modelo atual
    """
    manager = get_fallback_manager()

    # Tentar voltar ao primário após cooldown
    if manager.should_try_primary():
        manager.reset_to_primary()

    return manager.get_model(temperature)


def is_rate_limit_error(exception: Exception) -> bool:
    """
    Verifica se uma exceção é um erro de rate limit (429).

    Args:
        exception: Exceção a ser verificada

    Returns:
        bool: True se é erro 429
    """
    error_msg = str(exception).lower()

    # Checar por indicadores de rate limit
    rate_limit_indicators = [
        "429",
        "rate limit",
        "rate_limit",
        "quota exceeded",
        "resource has been exhausted",
        "too many requests",
        "resourceexhausted",
    ]

    return any(indicator in error_msg for indicator in rate_limit_indicators)


def run_with_fallback(
    func: Callable,
    *args,
    max_retries: int = MAX_RETRIES_PER_MODEL,
    **kwargs
) -> Any:
    """
    Executa uma função com retry automático e fallback de modelo em caso de 429.

    Esta função:
    1. Tenta executar a função passada
    2. Em caso de erro 429, faz retry com backoff exponencial
    3. Se esgotar retries, alterna para próximo modelo na chain
    4. Repete até sucesso ou esgotar todos os modelos

    Args:
        func: Função a ser executada (ex: agent.run)
        *args: Argumentos posicionais para a função
        max_retries: Máximo de retries por modelo antes de fazer fallback
        **kwargs: Argumentos nomeados para a função

    Returns:
        Resultado da função executada

    Raises:
        Exception: Re-levanta a última exceção se todos os modelos falharem
    """
    manager = get_fallback_manager()
    last_exception = None

    # Tentar voltar ao primário se cooldown passou
    if manager.should_try_primary():
        manager.reset_to_primary()

    # Loop através dos modelos na chain
    while True:
        current_model = manager.current_model_id

        # Retry loop para o modelo atual
        for retry in range(max_retries):
            try:
                result = func(*args, **kwargs)

                # Sucesso! Resetar contador de erros do modelo
                manager.error_counts[current_model] = 0
                return result

            except Exception as e:
                last_exception = e

                if is_rate_limit_error(e):
                    manager.record_error(current_model)

                    if retry < max_retries - 1:
                        # Backoff exponencial antes de retry
                        backoff = min(
                            INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** retry),
                            MAX_BACKOFF_SECONDS
                        )
                        logger.warning(
                            f"⏳ Rate limit em {current_model}. "
                            f"Retry {retry + 1}/{max_retries} em {backoff}s..."
                        )
                        time.sleep(backoff)
                    else:
                        # Esgotar retries para este modelo, tentar próximo
                        logger.warning(
                            f"❌ Esgotaram {max_retries} retries em {current_model}. "
                            f"Tentando fallback..."
                        )
                else:
                    # Erro não relacionado a rate limit, re-levantar imediatamente
                    logger.error(f"❌ Erro não-related a rate limit: {e}")
                    raise

        # Tentar próximo modelo na chain
        if not manager.switch_to_next_model():
            # Não há mais modelos, re-levantar última exceção
            logger.error("💀 Todos os modelos na chain de fallback falharam!")
            raise last_exception


# ============================================================================
# DECORATOR PARA FUNÇÕES COM FALLBACK AUTOMÁTICO
# ============================================================================

def with_model_fallback(max_retries: int = MAX_RETRIES_PER_MODEL):
    """
    Decorator que adiciona retry com fallback automático a uma função.

    Uso:
        @with_model_fallback(max_retries=3)
        def minha_funcao_com_llm(prompt):
            agent = Agent(model=get_model_with_fallback())
            return agent.run(prompt)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return run_with_fallback(func, *args, max_retries=max_retries, **kwargs)
        return wrapper
    return decorator

# Testes movidos para tests/test_gemini_fallback.py
