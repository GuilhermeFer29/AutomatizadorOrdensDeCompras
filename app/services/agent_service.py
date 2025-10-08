"""Serviço para execução do grafo de agentes de cadeia de suprimentos."""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog
from langgraph.graph import CompiledGraph

from app.agents.supply_chain_graph import SupplyChainState, build_supply_chain_graph

LOGGER = structlog.get_logger(__name__)
_COMPILED_GRAPH: Optional[CompiledGraph] = None


def _get_compiled_graph() -> CompiledGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        LOGGER.info("agents.graph.building")
        _COMPILED_GRAPH = build_supply_chain_graph().compile()
        LOGGER.info("agents.graph.ready")
    return _COMPILED_GRAPH


def _initial_state(*, sku: str, inquiry_reason: Optional[str]) -> SupplyChainState:
    state: SupplyChainState = {"product_sku": sku}
    if inquiry_reason:
        state["inquiry_reason"] = inquiry_reason
    return state


def execute_supply_chain_analysis(
    *, sku: str, inquiry_reason: Optional[str] = None
) -> Dict[str, Any]:
    """Executa o grafo de agentes e retorna o estado final consolidado."""

    if not sku.strip():
        raise ValueError("O SKU informado não pode ser vazio.")

    graph = _get_compiled_graph()
    initial_state = _initial_state(sku=sku.strip(), inquiry_reason=inquiry_reason)

    LOGGER.info("agents.analysis.start", sku=sku, inquiry_reason=inquiry_reason)
    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:  # noqa: BLE001 - queremos propagar a mensagem original
        LOGGER.exception("agents.analysis.error", sku=sku, error=str(exc))
        raise

    LOGGER.info("agents.analysis.completed", sku=sku)

    result: Dict[str, Any] = dict(final_state)
    result.setdefault("product_sku", sku)
    result.setdefault("inquiry_reason", inquiry_reason)
    result.setdefault("forecast", {})
    result.setdefault("need_restock", False)
    result.setdefault("market_prices", [])
    result.setdefault("logistics_analysis", {})

    return result


__all__ = ["execute_supply_chain_analysis"]
