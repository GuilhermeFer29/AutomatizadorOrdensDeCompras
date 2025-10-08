"""Grafo de agentes colaborativos para análise e recomendação de compras."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, TypedDict

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from app.agents.tools import SUPPLY_CHAIN_TOOLS


class SupplyChainState(TypedDict, total=False):
    product_sku: str
    inquiry_reason: Optional[str]
    product_snapshot: Dict[str, object]
    forecast: Dict[str, object]
    need_restock: bool
    forecast_notes: str
    market_prices: List[Dict[str, object]]
    logistics_analysis: Dict[str, object]
    recommendation: Dict[str, object]


DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-chat-v3.1:free"
DEFAULT_OPENROUTER_BASE_URL = "https://api.openrouter.ai"


def _build_llm(agent_name: str) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Variável de ambiente 'OPENROUTER_API_KEY' não configurada. "
            "Defina a chave de API no arquivo .env ou nas variáveis de ambiente do servidor."
        )

    model_name = os.getenv("OPENROUTER_MODEL_NAME", DEFAULT_OPENROUTER_MODEL)
    base_url = os.getenv("OPENROUTER_API_BASE", DEFAULT_OPENROUTER_BASE_URL)

    return ChatOpenAI(
        model=model_name,
        temperature=0.2,
        streaming=False,
        model_kwargs={"provider": "openrouter"},
        openai_api_key=api_key,
        base_url=base_url,
    ).with_config({"run_name": agent_name})


def _select_tools(*tool_names: str):
    tool_map = {tool.name: tool for tool in SUPPLY_CHAIN_TOOLS}
    return [tool_map[name] for name in tool_names if name in tool_map]


def _build_agent(agent_name: str, system_prompt: str, tool_names: List[str]) -> AgentExecutor:
    tools = _select_tools(*tool_names)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "user",
                "Contexto atual da análise (JSON):\n```json\n{state_json}\n```\n"
                "Forneça somente a saída final em JSON válido seguindo o formato solicitado.",
            ),
        ]
    )
    llm = _build_llm(agent_name)
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)


def _invoke_agent(agent: AgentExecutor, *, state: SupplyChainState) -> Dict[str, object]:
    filtered_state = {k: v for k, v in state.items() if v is not None}
    result = agent.invoke({"state_json": json.dumps(filtered_state, ensure_ascii=False)})
    output_text: str = result["output"]
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Resposta do agente não está em JSON válido: {output_text}") from exc


ANALISTA_DEMANDA_PROMPT = (
    "Você é o Analista de Demanda. Avalie estoque e histórico para projetar consumo futuro. "
    "Utilize as ferramentas `lookup_product` e `load_demand_forecast` para embasar sua decisão. "
    "Retorne somente JSON com `forecast_summary` (objeto), `need_restock` (bool) e `justification` (texto)."
)

PESQUISADOR_MERCADO_PROMPT = (
    "Você é o Pesquisador de Mercado. Se `need_restock` for verdadeiro, execute `scrape_latest_price` para coletar preços atualizados. "
    "Retorne apenas JSON com `offers`, uma lista de objetos contendo `source`, `price`, `currency` e `coletado_em`. "
    "Caso não seja necessária reposição, devolva `offers` como lista vazia."
    
)

ANALISTA_LOGISTICA_PROMPT = (
    "Você é o Analista de Logística. Avalie forecast e ofertas para selecionar o melhor fornecedor. "
    "Utilize `compute_distance` quando houver coordenadas ou distâncias a calcular. "
    "Responda em JSON com `selected_offer` (objeto ou null) e `analysis_notes` (texto explicativo)."
    
)

GERENTE_COMPRAS_PROMPT = (
    "Você é o Gerente de Compras. Una todas as análises e produza uma recomendação final. "
    "Responda somente em JSON com `decision`, `supplier`, `price`, `currency`, `rationale` e `next_steps` (lista)."
)


def build_supply_chain_graph() -> StateGraph:
    graph = StateGraph(SupplyChainState)

    analista_demanda = _build_agent(
        agent_name="AnalistaDemanda",
        system_prompt=ANALISTA_DEMANDA_PROMPT,
        tool_names=["lookup_product", "load_demand_forecast"],
    )

    pesquisador_mercado = _build_agent(
        agent_name="PesquisadorMercado",
        system_prompt=PESQUISADOR_MERCADO_PROMPT,
        tool_names=["scrape_latest_price"],
    )

    analista_logistica = _build_agent(
        agent_name="AnalistaLogistica",
        system_prompt=ANALISTA_LOGISTICA_PROMPT,
        tool_names=["compute_distance"],
    )

    gerente_compras = _build_agent(
        agent_name="GerenteCompras",
        system_prompt=GERENTE_COMPRAS_PROMPT,
        tool_names=[],
    )

    def demanda_node(state: SupplyChainState) -> SupplyChainState:
        output = _invoke_agent(analista_demanda, state=state)
        state["forecast"] = output.get("forecast_summary", {})
        state["need_restock"] = bool(output.get("need_restock", False))
        state["forecast_notes"] = output.get("justification", "")
        return state

    def mercado_node(state: SupplyChainState) -> SupplyChainState:
        if not state.get("need_restock"):
            state["market_prices"] = []
            return state
        output = _invoke_agent(pesquisador_mercado, state=state)
        state["market_prices"] = output.get("offers", [])
        return state

    def logistica_node(state: SupplyChainState) -> SupplyChainState:
        output = _invoke_agent(analista_logistica, state=state)
        state["logistics_analysis"] = {
            "selected_offer": output.get("selected_offer"),
            "analysis_notes": output.get("analysis_notes"),
        }
        return state

    def gerente_node(state: SupplyChainState) -> SupplyChainState:
        output = _invoke_agent(gerente_compras, state=state)
        state["recommendation"] = output
        return state

    graph.add_node("analista_demanda", demanda_node)
    graph.add_node("pesquisador_mercado", mercado_node)
    graph.add_node("analista_logistica", logistica_node)
    graph.add_node("gerente_compras", gerente_node)

    graph.set_entry_point("analista_demanda")
    graph.add_edge("analista_demanda", "pesquisador_mercado")
    graph.add_edge("pesquisador_mercado", "analista_logistica")
    graph.add_edge("analista_logistica", "gerente_compras")
    graph.add_edge("gerente_compras", END)

    return graph


__all__ = ["SupplyChainState", "build_supply_chain_graph"]