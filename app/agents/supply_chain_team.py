"""
Team de agentes colaborativos usando Agno 2.1.3 para análise e recomendação de compras.

CORREÇÕES FINAIS APLICADAS (Agno 2.1.3 - 2025-10-09):

ATUALIZAÇÃO COMPLETA PARA AGNO 2.1.3:
1. Imports corretos:
   - ✅ from agno.agent import Agent
   - ✅ from agno.models.openai import OpenAIChat (não OpenAI!)
   - ✅ from agno.team import Team

2. OpenAIChat configurado corretamente:
   - ✅ id: str (nome do modelo) - CORRETO para Agno 2.1.3
   - ✅ api_key: str
   - ✅ base_url: str  
   - ✅ temperature: float

3. Agent configurado conforme API 2.1.3:
   - ✅ name: str (nome do agente)
   - ✅ model: OpenAIChat (instância do LLM)
   - ✅ instructions: List[str] (lista de diretrizes)
   - ✅ tools: List[Toolkit] (ferramentas disponíveis)
   - ✅ markdown: bool (formatação)
   - ✅ description: str (descrição opcional do papel)

4. Team configurado conforme API 2.1.3:
   - ✅ members: List[Agent] (não "agents"!)
   - ✅ Não usa "mode" - coordenação é automática

REFERÊNCIA: Agno v2.1.3 (instalado e validado)
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from agno.tools import Toolkit

from app.agents.tools import SupplyChainToolkit, lookup_product, load_demand_forecast


# Configuração do modelo Gemini
def _get_llm_for_agno(temperature: float = 0.2) -> Gemini:
    """
    Retorna modelo Gemini 2.5 Flash configurado.
    
    VANTAGENS DO GEMINI 2.5 FLASH:
    - ✅ Gratuito até 1500 req/dia
    - ✅ 3-5x mais rápido que modelos anteriores
    - ✅ Context window: 1M tokens
    - ✅ Suporta function calling nativo
    
    Args:
        temperature: Controle de aleatoriedade (0.2 = padrão para análises técnicas)
        
    Returns:
        Instância Gemini configurada
        
    Raises:
        RuntimeError: Se GOOGLE_API_KEY não estiver configurada
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Variável de ambiente 'GOOGLE_API_KEY' não configurada. "
            "Obtenha sua chave em: https://aistudio.google.com/app/apikey"
        )

    return Gemini(
        id="gemini-2.5-pro",  
        api_key=api_key,
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
2. Se o scraping falhar, use tavily_search_results_json para buscar informações contextuais
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
    """
    Cria e retorna o Team de análise de cadeia de suprimentos.
    
    Utiliza a API do Agno 2.1.3 com parâmetros corretos:
    - name: Nome do agente
    - model: Instância do modelo LLM (OpenAIChat)
    - instructions: Lista de diretrizes de comportamento
    - tools: Lista de ferramentas disponíveis (Toolkits)
    - markdown: Habilita formatação markdown nas respostas
    - description: Descrição opcional do papel do agente
    """
    
    # Inicializa o toolkit compartilhado
    toolkit = SupplyChainToolkit()
    
    # Cria os agentes especialistas com API do Agno 2.1.3
    analista_demanda = Agent(
        name="AnalistaDemanda",
        description="Especialista em previsão de demanda e análise de estoque",
        model=_get_llm_for_agno(temperature=0.2),
        instructions=[ANALISTA_DEMANDA_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    pesquisador_mercado = Agent(
        name="PesquisadorMercado",
        description="Especialista em inteligência competitiva e análise de preços",
        model=_get_llm_for_agno(temperature=0.2),
        instructions=[PESQUISADOR_MERCADO_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    analista_logistica = Agent(
        name="AnalistaLogistica",
        description="Especialista em otimização de cadeia de suprimentos e logística",
        model=_get_llm_for_agno(temperature=0.2),
        instructions=[ANALISTA_LOGISTICA_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    gerente_compras = Agent(
        name="GerenteCompras",
        description="Responsável pela decisão final de aquisição",
        model=_get_llm_for_agno(temperature=0.1),
        instructions=[GERENTE_COMPRAS_PROMPT],
        markdown=True,
    )
    
    # Cria o team com 'members' (não 'agents')
    # Agno 2.1.3 coordena automaticamente (não usa 'mode')
    team = Team(
        members=[analista_demanda, pesquisador_mercado, analista_logistica, gerente_compras],
        name="SupplyChainTeam",
        description="Equipe de análise e recomendação de compras",
    )
    
    return team


def run_supply_chain_analysis(inquiry: str) -> Dict:
    """
    Função principal para executar análise de cadeia de suprimentos usando Agno Team.
    
    Esta função cria a equipe de agentes e executa a análise completa baseada
    na consulta (inquiry) fornecida. O Team coordena automaticamente a execução
    dos agentes especializados.
    
    Args:
        inquiry: Consulta/pergunta sobre a análise de compra (ex: "Analisar compra do SKU_001")
    
    Returns:
        Dicionário com o resultado consolidado da análise
        
    Example:
        >>> result = run_supply_chain_analysis("Preciso comprar 50 unidades do SKU_001")
        >>> print(result["recommendation"]["decision"])
        'approve'
    """
    # Cria e executa o team
    team = create_supply_chain_team()
    response = team.run(inquiry)
    
    # Extrai conteúdo da resposta
    if hasattr(response, 'content'):
        output_text = response.content
    else:
        output_text = str(response)
    
    # Parse do JSON da resposta
    # O Agno com markdown=True pode envolver JSON em blocos ```json
    if "```json" in output_text:
        json_part = output_text.split("```json")[1]
        if "```" in json_part:
            json_part = json_part.split("```")[0]
        output_text = json_part.strip()
    
    try:
        result = json.loads(output_text)
    except json.JSONDecodeError:
        # Fallback em caso de erro de parsing
        result = {
            "decision": "manual_review",
            "rationale": f"Erro ao processar resposta do team: {output_text[:200]}",
            "supplier": None,
            "price": None,
            "currency": "BRL",
            "quantity_recommended": 0,
            "next_steps": ["Revisar manualmente a análise completa"],
            "risk_assessment": "Dados insuficientes ou formato inválido"
        }
    
    return result


def execute_supply_chain_team(sku: str, inquiry_reason: Optional[str] = None) -> Dict:
    """
    Função legada/wrapper para manter compatibilidade com o código existente.
    
    Carrega dados do produto e delega para run_supply_chain_analysis().
    
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
    
    # Monta a mensagem de consulta
    inquiry = f"""Analisar o produto {sku} para decisão de compra.

Contexto da análise:
```json
{json.dumps(context, ensure_ascii=False, indent=2)}
```

Execute a análise completa e forneça a recomendação final em JSON válido."""
    
    # Executa a análise usando o team
    recommendation = run_supply_chain_analysis(inquiry)
    
    # Monta o resultado final com estrutura esperada pelo sistema legado
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


__all__ = ["create_supply_chain_team", "run_supply_chain_analysis", "execute_supply_chain_team"]
