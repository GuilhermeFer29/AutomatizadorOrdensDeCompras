"""Serviço para execução do team de agentes de cadeia de suprimentos."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlmodel import Session, select

from app.agents.supply_chain_team import execute_supply_chain_team
from app.models.models import Agente

LOGGER = structlog.get_logger(__name__)

def get_agents(session: Session):
    agents = session.exec(select(Agente)).all()

    if not agents:
        default_agents = [
            Agente(
                nome="Agente de Previsão de Preços",
                descricao="Analisa tendências de mercado e prevê flutuações de preços",
                status="active",
            ),
            Agente(
                nome="Agente de Compras Automáticas",
                descricao="Executa ordens de compra baseadas nas previsões do modelo",
                status="active",
            ),
            Agente(
                nome="Agente de Monitoramento de Estoque",
                descricao="Monitora níveis de estoque e dispara alertas quando necessário",
                status="inactive",
            ),
            Agente(
                nome="Agente de Análise de Fornecedores",
                descricao="Avalia performance de fornecedores e identifica oportunidades",
                status="active",
            ),
        ]

        session.add_all(default_agents)
        session.commit()
        agents = session.exec(select(Agente)).all()

    return agents

def toggle_agent_status(session: Session, agent_id: int, action: str):
    agent = session.get(Agente, agent_id)
    if not agent:
        return None
    agent.status = 'active' if action == 'activate' else 'inactive'
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent

from app.tasks.agent_tasks import execute_agent_analysis_task


def run_agent_now(session: Session, agent_id: int):
    agent = session.get(Agente, agent_id)
    if not agent:
        return None

    # Dispara a tarefa em segundo plano
    # Para este exemplo, vamos assumir que o agente opera sobre um SKU de produto.
    # Como não temos um SKU direto no agente, vamos usar um mock ou o primeiro produto.
    # Em um cenário real, o agente teria uma configuração mais específica.
    from app.models.models import Produto
    produto = session.exec(select(Produto)).first()
    if produto:
        execute_agent_analysis_task.delay(sku=produto.sku)

    agent.ultima_execucao = datetime.now(UTC)
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent

def execute_supply_chain_analysis(
    *, sku: str, inquiry_reason: str | None = None
) -> dict[str, Any]:
    """Executa o team de agentes Agno e retorna o estado final consolidado."""

    if not sku.strip():
        raise ValueError("O SKU informado não pode ser vazio.")

    LOGGER.info("agents.analysis.start", sku=sku, inquiry_reason=inquiry_reason)
    try:
        result = execute_supply_chain_team(sku=sku.strip(), inquiry_reason=inquiry_reason)
    except Exception as exc:  # noqa: BLE001 - queremos propagar a mensagem original
        LOGGER.exception("agents.analysis.error", sku=sku, error=str(exc))
        raise

    LOGGER.info("agents.analysis.completed", sku=sku)

    # Garante que os campos essenciais existem
    result.setdefault("product_sku", sku)
    result.setdefault("inquiry_reason", inquiry_reason)
    result.setdefault("forecast", {})
    result.setdefault("need_restock", False)
    result.setdefault("market_prices", [])
    result.setdefault("logistics_analysis", {})

    return result

def run_purchase_analysis(sku: str):
    """
    Executa análise da cadeia de suprimentos para um determinado SKU.

    Args:
        sku (str): O SKU do produto a ser analisado.

    Returns:
        dict: O estado final após a execução.
    """
    return execute_supply_chain_analysis(sku=sku)

__all__ = ["execute_supply_chain_analysis", "get_agents", "toggle_agent_status", "run_agent_now", "run_purchase_analysis"]
