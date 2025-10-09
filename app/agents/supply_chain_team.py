"""Team de agentes colaborativos usando Agno para análise e recomendação de compras."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from agno.agent import Agent
from agno.models.openai import OpenAI
from agno.team import Team

from app.agents.tools import SupplyChainToolkit, lookup_product, load_demand_forecast


# Configuração do modelo OpenRouter
def _get_openai_model(temperature: float = 0.2) -> OpenAI:
    """Retorna modelo OpenAI configurado para usar OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Variável de ambiente 'OPENROUTER_API_KEY' não configurada. "
            "Defina a chave de API no arquivo .env ou nas variáveis de ambiente do servidor."
        )

    model_name = os.getenv("OPENROUTER_MODEL_NAME", "mistralai/mistral-small-3.1-24b-instruct:free")
    base_url = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

    return OpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )


# Prompts dos agentes especialistas
ANALISTA_DEMANDA_PROMPT = """Você é o Analista de Demanda, especialista em previsão e análise de estoque.

## Papel e Responsabilidades
Analise os dados de produto e previsão de demanda para determinar a necessidade de reposição de estoque.

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
```"""

PESQUISADOR_MERCADO_PROMPT = """Você é o Pesquisador de Mercado, especialista em inteligência competitiva e análise de preços.

## Papel e Responsabilidades
Coletar e analisar dados atualizados de mercado sobre preços e fornecedores.

## Diretrizes de Resiliência
1. Se `need_restock` for falso, retorne offers vazio
2. Se o scraping falhar, tente buscar informações contextuais com busca web ou Wikipedia
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
```"""

ANALISTA_LOGISTICA_PROMPT = """Você é o Analista de Logística, especialista em otimização de cadeia de suprimentos.

## Papel e Responsabilidades
Avaliar ofertas de fornecedores considerando custos logísticos, distâncias e prazos.

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
```"""

GERENTE_COMPRAS_PROMPT = """Você é o Gerente de Compras, responsável pela decisão final de aquisição.

## Papel e Responsabilidades
Consolidar todas as análises anteriores e produzir uma recomendação final de compra.

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
```"""


def create_supply_chain_team() -> Team:
    """Cria e retorna o Team de análise de cadeia de suprimentos."""
    
    # Inicializa o toolkit
    toolkit = SupplyChainToolkit()
    
    # Cria os agentes especialistas
    analista_demanda = Agent(
        name="AnalistaDemanda",
        model=_get_openai_model(temperature=0.2),
        instructions=ANALISTA_DEMANDA_PROMPT,
        tools=[toolkit],
        markdown=False,
    )
    
    pesquisador_mercado = Agent(
        name="PesquisadorMercado",
        model=_get_openai_model(temperature=0.2),
        instructions=PESQUISADOR_MERCADO_PROMPT,
        tools=[toolkit],
        markdown=False,
    )
    
    analista_logistica = Agent(
        name="AnalistaLogistica",
        model=_get_openai_model(temperature=0.2),
        instructions=ANALISTA_LOGISTICA_PROMPT,
        tools=[toolkit],
        markdown=False,
    )
    
    gerente_compras = Agent(
        name="GerenteCompras",
        model=_get_openai_model(temperature=0.1),
        instructions=GERENTE_COMPRAS_PROMPT,
        markdown=False,
    )
    
    # Cria o team com fluxo sequencial
    team = Team(
        name="SupplyChainTeam",
        agents=[analista_demanda, pesquisador_mercado, analista_logistica, gerente_compras],
        mode="sequential",  # Execução sequencial como no LangGraph
    )
    
    return team


def execute_supply_chain_team(sku: str, inquiry_reason: Optional[str] = None) -> Dict:
    """
    Executa o team de análise de cadeia de suprimentos para um SKU.
    
    Args:
        sku: SKU do produto a ser analisado
        inquiry_reason: Motivo da consulta (opcional)
    
    Returns:
        Dicionário com o resultado da análise e recomendação
    """
    if not sku.strip():
        raise ValueError("O SKU informado não pode ser vazio.")
    
    # Carrega dados iniciais do produto
    product_data = lookup_product(sku)
    forecast_data = load_demand_forecast(sku)
    
    # Monta o contexto inicial
    context = {
        "product_sku": sku,
        "inquiry_reason": inquiry_reason,
        "product_snapshot": product_data,
        "forecast": forecast_data,
    }
    
    # Monta a mensagem inicial para o team
    initial_message = f"""Analisar o produto {sku} para decisão de compra.

Contexto da análise (JSON):
```json
{json.dumps(context, ensure_ascii=False, indent=2)}
```

Por favor, execute a análise completa seguindo o fluxo sequencial:
1. Análise de Demanda
2. Pesquisa de Mercado
3. Análise Logística
4. Decisão Final de Compra

Forneça somente a saída final em JSON válido seguindo o formato solicitado."""
    
    # Cria o team
    team = create_supply_chain_team()
    
    # Executa o team
    response = team.run(initial_message)
    
    # Extrai o resultado
    if hasattr(response, 'content'):
        output_text = response.content
    else:
        output_text = str(response)
    
    # Parse do resultado JSON
    if "```json" in output_text:
        json_part = output_text.split("```json")[1]
        if "```" in json_part:
            json_part = json_part.split("```")[0]
        output_text = json_part.strip()
    
    try:
        recommendation = json.loads(output_text)
    except json.JSONDecodeError:
        # Fallback se não conseguir fazer parse
        recommendation = {
            "decision": "manual_review",
            "rationale": f"Erro ao processar resposta: {output_text[:200]}",
            "supplier": None,
            "price": None,
            "currency": "BRL",
            "quantity_recommended": 0,
            "next_steps": ["Revisar manualmente a análise"],
            "risk_assessment": "Dados insuficientes"
        }
    
    # Monta o resultado final
    result = {
        "product_sku": sku,
        "inquiry_reason": inquiry_reason,
        "product_snapshot": product_data,
        "forecast": forecast_data,
        "need_restock": recommendation.get("decision") == "approve",
        "forecast_notes": recommendation.get("rationale", ""),
        "market_prices": recommendation.get("offers", []),
        "logistics_analysis": {
            "selected_offer": recommendation.get("selected_offer"),
            "analysis_notes": recommendation.get("analysis_notes", ""),
        },
        "recommendation": recommendation,
    }
    
    return result


__all__ = ["create_supply_chain_team", "execute_supply_chain_team"]
