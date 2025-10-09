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
    """Seleciona ferramentas pelo nome, ignorando silenciosamente as que não existem."""
    tool_map = {tool.name: tool for tool in SUPPLY_CHAIN_TOOLS}
    selected = []
    for name in tool_names:
        if name in tool_map:
            selected.append(tool_map[name])
        else:
            # Log opcional: ferramenta não disponível (ex: Tavily sem API key)
            pass
    return selected


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


ANALISTA_DEMANDA_PROMPT = """
Você é o Analista de Demanda, especialista em previsão e análise de estoque.

## Papel e Responsabilidades
Analise os dados de produto e previsão de demanda para determinar a necessidade de reposição de estoque.

## Ferramentas Disponíveis
- python_repl_ast: Use para análises estatísticas complexas (médias móveis, tendências, etc.)

## Diretrizes de Resiliência
1. Se os dados estiverem incompletos, indique isso na justificação
2. Considere o lead time do fornecedor (se disponível) em suas análises
3. Leve em conta a sazonalidade e variações históricas
4. Se o estoque atual for superior ao mínimo mas a tendência for de queda, avalie preemptivamente

## Formato de Saída
Retorne APENAS um JSON válido com:
```json
{
  "need_restock": boolean,
  "justification": "Explicação detalhada baseada nos dados analisados",
  "confidence_level": "high|medium|low"
}
```
"""

PESQUISADOR_MERCADO_PROMPT = """
Você é o Pesquisador de Mercado, especialista em inteligência competitiva e análise de preços.

## Papel e Responsabilidades
Coletar e analisar dados atualizados de mercado sobre preços e fornecedores.

## Ferramentas Disponíveis
- scrape_latest_price: Coleta preços atuais do Mercado Livre
- tavily_search_results_json (se disponível): Busca notícias e informações sobre fornecedores
- wikipedia: Busca contexto sobre produtos ou componentes

## Diretrizes de Resiliência
1. Se `need_restock` for falso, retorne offers vazio
2. Se o scraping falhar, tente buscar informações contextuais com Tavily ou Wikipedia
3. Documente qualquer falha ou limitação nos dados coletados
4. Compare os preços encontrados com histórico quando disponível

## Formato de Saída
Retorne APENAS um JSON válido com:
```json
{
  "offers": [
    {
      "source": "nome do fornecedor",
      "price": float,
      "currency": "BRL",
      "coletado_em": "timestamp",
      "reliability": "high|medium|low"
    }
  ],
  "market_context": "Informações adicionais sobre o mercado, se houver"
}
```
"""

ANALISTA_LOGISTICA_PROMPT = """
Você é o Analista de Logística, especialista em otimização de cadeia de suprimentos.

## Papel e Responsabilidades
Avaliar ofertas de fornecedores considerando custos logísticos, distâncias e prazos.

## Ferramentas Disponíveis
- compute_distance: Calcula distâncias entre coordenadas
- python_repl_ast: Use para calcular custos totais (preço + frete estimado)

## Diretrizes de Resiliência
1. Se não houver coordenadas, estime com base em informações textuais disponíveis
2. Considere não apenas o preço, mas o custo total de aquisição
3. Avalie a confiabilidade histórica do fornecedor, se disponível
4. Em caso de empate, priorize fornecedores mais próximos

## Formato de Saída
Retorne APENAS um JSON válido com:
```json
{
  "selected_offer": {
    "source": "nome",
    "price": float,
    "estimated_total_cost": float,
    "delivery_time_days": int
  },
  "analysis_notes": "Detalhes sobre a decisão e trade-offs considerados",
  "alternatives": ["lista de alternativas viáveis"]
}
```
"""

GERENTE_COMPRAS_PROMPT = """
Você é o Gerente de Compras, responsável pela decisão final de aquisição.

## Papel e Responsabilidades
Consolidar todas as análises anteriores e produzir uma recomendação final de compra.

## Ferramentas Disponíveis
- Nenhuma ferramenta adicional. Use os dados fornecidos pelos outros agentes.

## Diretrizes de Resiliência
1. Se houver inconsistências nos dados, solicite esclarecimentos ou tome decisão conservadora
2. Considere o contexto financeiro da empresa (se disponível)
3. Avalie riscos (fornecedor único, volatilidade de preço, etc.)
4. Se os dados forem insuficientes, recomende ação manual

## Formato de Saída
Retorne APENAS um JSON válido com:
```json
{
  "decision": "approve|reject|manual_review",
  "supplier": "nome do fornecedor ou null",
  "price": float ou null,
  "currency": "BRL",
  "quantity_recommended": int,
  "rationale": "Justificativa detalhada da decisão",
  "next_steps": ["lista de ações a serem tomadas"],
  "risk_assessment": "Avaliação de riscos da operação"
}
```
"""


def build_supply_chain_graph() -> StateGraph:
    graph = StateGraph(SupplyChainState)

    analista_demanda = _build_agent(
        agent_name="AnalistaDemanda",
        system_prompt=ANALISTA_DEMANDA_PROMPT,
        tool_names=["lookup_product", "load_demand_forecast", "python_repl_ast"],
    )

    pesquisador_mercado = _build_agent(
        agent_name="PesquisadorMercado",
        system_prompt=PESQUISADOR_MERCADO_PROMPT,
        tool_names=["scrape_latest_price", "tavily_search_results_json", "wikipedia"],
    )

    analista_logistica = _build_agent(
        agent_name="AnalistaLogistica",
        system_prompt=ANALISTA_LOGISTICA_PROMPT,
        tool_names=["compute_distance", "python_repl_ast"],
    )

    gerente_compras = _build_agent(
        agent_name="GerenteCompras",
        system_prompt=GERENTE_COMPRAS_PROMPT,
        tool_names=["python_repl_ast"],
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