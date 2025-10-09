"""Grafo de agentes colaborativos para análise e recomendação de compras."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, TypedDict

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph

from app.agents.tools import (
    SUPPLY_CHAIN_TOOLS,
    load_demand_forecast,
    lookup_product,
)


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


DEFAULT_OPENROUTER_MODEL = "mistralai/mistral-small-3.1-24b-instruct:free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    llm = _build_llm(agent_name)
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)


def _invoke_agent(agent: AgentExecutor, *, state: SupplyChainState) -> Dict[str, object]:
    filtered_state = {k: v for k, v in state.items() if v is not None}
    result = agent.invoke({"state_json": json.dumps(filtered_state, ensure_ascii=False)})
    output_text: str = result["output"]

    if "```json" in output_text:
        json_part = output_text.split("```json")[1]
        if "```" in json_part:
            json_part = json_part.split("```")[0]
        output_text = json_part.strip()

    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Resposta do agente não está em JSON válido: {output_text}") from exc


ANALISTA_DEMANDA_PROMPT = (
    "Você é o Analista de Demanda. Com base nos dados de produto e previsão de demanda fornecidos no contexto, "
    "sua tarefa é determinar se a reposição de estoque é necessária. "
    "Retorne apenas um JSON com a estrutura: "
    "`need_restock` (bool) e `justification` (texto curto explicando sua decisão)."
)

PESQUISADOR_MERCADO_PROMPT = (
    "Você é o Pesquisador de Mercado. Se `need_restock` for verdadeiro, execute `scrape_latest_price` para coletar preços atualizados. "
    "Retorne apenas JSON com `offers`, uma lista de objetos contendo `source`, `price`, `currency` e `coletado_em`. "
    "Caso não seja necessária reposição, devolva `offers` como lista vazia, sem texto adicional."
)

ANALISTA_LOGISTICA_PROMPT = (
    "Você é o Analista de Logística. Avalie forecast e ofertas para selecionar o melhor fornecedor. "
    "Utilize `compute_distance` quando houver coordenadas ou distâncias a calcular. "
    "Responda somente em JSON com `selected_offer` (objeto ou null) e `analysis_notes` (texto explicativo)."
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
        tool_names=[],  # As ferramentas serão chamadas diretamente no nó
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
        sku = state["product_sku"]
        product_data = lookup_product(sku=sku)
        forecast_data = load_demand_forecast(sku=sku)

        state["product_snapshot"] = product_data
        state["forecast"] = forecast_data

        output = _invoke_agent(analista_demanda, state=state)
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