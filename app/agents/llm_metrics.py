"""
LLM Cost & Usage Metrics — Prometheus instrumentation for all Gemini calls.

Exposes the following metrics at ``/metrics``:

* ``llm_requests_total``             — Counter: total LLM calls by model, agent, status
* ``llm_request_duration_seconds``   — Histogram: latency per call
* ``llm_tokens_total``               — Counter: input/output tokens consumed
* ``llm_estimated_cost_usd``         — Counter: estimated USD cost (Gemini pricing)

Usage::

    from app.agents.llm_metrics import track_llm_call

    with track_llm_call(model="gemini-2.5-flash", agent="AnalistaDemanda"):
        result = agent.run(prompt)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

try:
    from prometheus_client import Counter, Histogram
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)

# ============================================================================
# Gemini pricing (USD per 1M tokens) — update when Google changes pricing
# Ref: https://ai.google.dev/gemini-api/docs/pricing
# Updated: 2026-02 (removed deprecated 2.0/1.5, added 2.5-lite and 3.x)
# ============================================================================
_PRICE_PER_1M_INPUT: dict[str, float] = {
    "gemini-2.5-flash": 0.15,
    "gemini-2.5-flash-lite": 0.05,
    "gemini-2.5-pro": 1.25,
    "gemini-3-flash-preview": 0.15,
    "gemini-3-pro-preview": 1.25,
}
_PRICE_PER_1M_OUTPUT: dict[str, float] = {
    "gemini-2.5-flash": 0.60,
    "gemini-2.5-flash-lite": 0.30,
    "gemini-2.5-pro": 10.00,
    "gemini-3-flash-preview": 0.60,
    "gemini-3-pro-preview": 10.00,
}

# ============================================================================
# Prometheus Metrics (only created if prometheus_client is installed)
# ============================================================================
if _HAS_PROMETHEUS:
    LLM_REQUESTS = Counter(
        "llm_requests_total",
        "Total LLM API calls",
        ["model", "agent", "status"],
    )
    LLM_DURATION = Histogram(
        "llm_request_duration_seconds",
        "LLM call latency in seconds",
        ["model", "agent"],
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
    )
    LLM_TOKENS = Counter(
        "llm_tokens_total",
        "Total tokens consumed",
        ["model", "direction"],  # direction = input | output
    )
    LLM_COST = Counter(
        "llm_estimated_cost_usd",
        "Estimated cost in USD",
        ["model"],
    )
else:
    LLM_REQUESTS = None  # type: ignore[assignment]
    LLM_DURATION = None  # type: ignore[assignment]
    LLM_TOKENS = None  # type: ignore[assignment]
    LLM_COST = None  # type: ignore[assignment]


def record_tokens(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record token usage and estimated cost for a single LLM call."""
    if not _HAS_PROMETHEUS:
        return

    if input_tokens:
        LLM_TOKENS.labels(model=model, direction="input").inc(input_tokens)
    if output_tokens:
        LLM_TOKENS.labels(model=model, direction="output").inc(output_tokens)

    # Cost estimation
    input_cost = (input_tokens / 1_000_000) * _PRICE_PER_1M_INPUT.get(model, 0.15)
    output_cost = (output_tokens / 1_000_000) * _PRICE_PER_1M_OUTPUT.get(model, 0.60)
    total_cost = input_cost + output_cost
    if total_cost > 0:
        LLM_COST.labels(model=model).inc(total_cost)


@contextmanager
def track_llm_call(
    model: str = "unknown",
    agent: str = "unknown",
) -> Generator[None, None, None]:
    """Context manager that tracks latency and success/failure of an LLM call.

    Example::

        with track_llm_call(model="gemini-2.5-flash", agent="AnalistaDemanda"):
            response = llm.invoke(prompt)
    """
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        if _HAS_PROMETHEUS:
            LLM_REQUESTS.labels(model=model, agent=agent, status=status).inc()
            LLM_DURATION.labels(model=model, agent=agent).observe(elapsed)
        logger.debug(
            "LLM call: model=%s agent=%s status=%s duration=%.2fs",
            model, agent, status, elapsed,
        )
