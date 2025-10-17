"""
Team de agentes colaborativos usando Agno 2.1.3 + Google Gemini 2.5 para análise e recomendação de compras.

ATUALIZAÇÃO PARA GEMINI 2.5 (2025-10-14):
==========================================

✅ MUDANÇAS APLICADAS:
1. Migração completa para modelos Google AI 2.5
2. Importação centralizada via app.agents.llm_config
3. Uso exclusivo de get_gemini_llm() para configuração do LLM
4. Padronização de todos os agentes com Gemini 2.5 Flash
5. Documentação atualizada com novos modelos

📋 STACK ATUAL (Google AI 2.5):
================================
- LLM: Google Gemini 2.5 Flash (models/gemini-2.5-flash)
- Framework: Agno 2.1.3
- Embeddings: Google text-embedding-004 (via rag_service.py)
- Tools: SupplyChainToolkit customizado

🎯 AGENTES ESPECIALIZADOS:
==========================
1. Analista de Demanda: Previsão e análise de estoque
2. Pesquisador de Mercado: Coleta de preços e inteligência competitiva
3. Analista de Logística: Otimização de fornecedores e custos
4. Gerente de Compras: Síntese e recomendação final

REFERÊNCIAS:
============
- Agno Docs: https://docs.agno.com/
- Gemini API: https://ai.google.dev/gemini-api/docs
- Config LLM: app/agents/llm_config.py
"""

from __future__ import annotations

import json
from typing import Dict, Optional

from agno.agent import Agent
from agno.team import Team
from agno.tools import Toolkit

# ✅ IMPORTAÇÃO CENTRALIZADA: LLMs otimizados por tipo de agente
from app.agents.llm_config import (
    get_gemini_for_fast_agents,      # Para agentes intermediários (Flash - rápido)
    get_gemini_for_decision_making   # Para decisões críticas (Pro - preciso)
)
from app.agents.tools import (
    SupplyChainToolkit,
    lookup_product,
    load_demand_forecast,
    search_market_trends_for_product,
    find_supplier_offers_for_sku,
    get_price_forecast_for_sku
)


# Prompts dos agentes especialistas
ANALISTA_DEMANDA_PROMPT = """Você é o Analista de Demanda, especialista em previsão e gestão de inventário.

## Papel e Responsabilidades
Avaliar o nível atual de estoque e recomendar se é necessário reabastecimento.

## Diretrizes de Resiliência 🛡️
1. **Se a previsão de demanda falhar**: Use o histórico de vendas médio dos últimos 30 dias
2. **Se não houver dados de vendas**: Considere estoque_minimo como referência segura
3. **Se apenas parte dos dados estiver disponível**: Faça uma recomendação CONSERVADORA baseada no que você tem
4. **NUNCA diga "não tenho dados"**: Sempre forneça uma análise com os dados disponíveis + AVISO sobre limitações

## Saída Esperada
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

## Ferramentas Disponíveis
1. **{find_supplier_offers_for_sku}**: Busca ofertas reais de fornecedores cadastrados
2. **{search_market_trends_for_product}**: Pesquisa tendências e notícias de mercado na web
3. **{get_price_forecast_for_sku}**: Obtém previsões ML de preços futuros

## Diretrizes de Resiliência
1. Se `need_restock` for falso, retorne offers vazio
2. SEMPRE use find_supplier_offers_for_sku primeiro para obter ofertas reais
3. Use search_market_trends_for_product para contexto de mercado
4. Compare as ofertas encontradas com previsões ML quando disponível
5. Documente qualquer falha ou limitação nos dados coletados

## Formato de Saída
Retorne APENAS um JSON válido com:
```json
{
  "offers": [
    {
      "fornecedor": "nome",
      "preco": float,
      "confiabilidade": float,
      "prazo_entrega_dias": int,
      "estoque_disponivel": int
    }
  ],
  "preco_medio": float,
  "melhor_oferta": {"fornecedor": "nome", "preco": float},
  "tendencias_mercado": "Resumo das tendências encontradas",
  "previsao_ml": "Tendência de preço segundo ML (alta/baixa/estável)"
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

## Diretrizes de Resiliência 🛡️
1. Se houver inconsistências nos dados, tome uma decisão conservadora com base no que você TEM
2. Considere o contexto financeiro da empresa (se disponível)
3. Avalie riscos (fornecedor único, volatilidade de preço, etc.)
4. **CRÍTICO**: Se uma análise anterior falhar (ex: previsão de demanda), use as informações DISPONÍVEIS (estoque atual, ofertas de mercado) para dar uma recomendação parcial e INTELIGENTE. NUNCA devolva o problema para o usuário. Diga o que você PODE fazer com os dados disponíveis e qual a CONFIANÇA da sua recomendação.
5. **Se dados críticos faltarem**: Marque decision="manual_review" MAS ainda forneça uma análise detalhada do que você CONSEGUIU avaliar

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
    Cria e retorna o Team de análise de cadeia de suprimentos usando Google Gemini 2.5.
    
    ✅ ARQUITETURA ATUALIZADA (Agno 2.1.3 + Gemini 2.5):
    - LLM: Google Gemini 2.5 Flash (configurado via get_gemini_llm())
    - Framework: Agno 2.1.3 com coordenação automática de agentes
    - Tools: SupplyChainToolkit customizado com 6 ferramentas especializadas
    - Output: JSON estruturado com recomendação de compra
    
    🎯 AGENTES ESPECIALIZADOS:
    1. Analista de Demanda (temp=0.2): Previsão e análise de estoque
    2. Pesquisador de Mercado (temp=0.2): Coleta de preços
    3. Analista de Logística (temp=0.2): Otimização de fornecedores
    4. Gerente de Compras (temp=0.1): Decisão final (mais determinístico)
    
    Returns:
        Team: Equipe configurada e pronta para análise
        
    Raises:
        ValueError: Se GOOGLE_API_KEY não estiver configurada
    """
    
    # ✅ CONFIGURAÇÃO OTIMIZADA: Flash (rápido) para intermediários, Pro (preciso) para decisões
    print("🚀 Configurando agentes com LLMs otimizados...")
    print("   - Flash (2-3x mais rápido): Analistas intermediários")
    print("   - Pro (mais preciso): Gerente de Compras e Team")
    
    fast_llm = get_gemini_for_fast_agents()      # Flash temp=0.2 (velocidade)
    decision_llm = get_gemini_for_decision_making()  # Pro temp=0.1 (precisão)
    
    # Inicializa o toolkit compartilhado (todas as ferramentas disponíveis)
    toolkit = SupplyChainToolkit()
    
    # ✅ AGENTE 1: Analista de Demanda (RÁPIDO)
    # Responsável por determinar SE precisamos comprar
    analista_demanda = Agent(
        name="AnalistaDemanda",
        description="Especialista em previsão de demanda e análise de estoque",
        model=fast_llm,  # ⚡ Flash - processamento rápido de dados estruturados
        instructions=[ANALISTA_DEMANDA_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    # ✅ AGENTE 2: Pesquisador de Mercado (RÁPIDO)
    # Responsável por encontrar ONDE e POR QUANTO comprar
    pesquisador_mercado = Agent(
        name="PesquisadorMercado",
        description="Especialista em inteligência competitiva e análise de preços",
        model=fast_llm,  # ⚡ Flash - busca e comparação rápida de ofertas
        instructions=[PESQUISADOR_MERCADO_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    # ✅ AGENTE 3: Analista de Logística (RÁPIDO)
    # Responsável por avaliar QUAL fornecedor é melhor (custo total)
    analista_logistica = Agent(
        name="AnalistaLogistica",
        description="Especialista em otimização de cadeia de suprimentos e logística",
        model=fast_llm,  # ⚡ Flash - cálculos logísticos rápidos
        instructions=[ANALISTA_LOGISTICA_PROMPT],
        tools=[toolkit],
        markdown=True,
    )
    
    # ✅ AGENTE 4: Gerente de Compras (PRECISO)
    # Responsável pela DECISÃO FINAL e síntese
    gerente_compras = Agent(
        name="GerenteCompras",
        description="Responsável pela decisão final de aquisição",
        model=decision_llm,  # 🎯 Pro - raciocínio profundo para decisões críticas
        instructions=[GERENTE_COMPRAS_PROMPT],
        markdown=True,
    )
    
    # ✅ COORDENAÇÃO AUTOMÁTICA: Agno 2.1.3 gerencia a ordem de execução
    # O Team executa os agentes na sequência ideal automaticamente
    team = Team(
        members=[analista_demanda, pesquisador_mercado, analista_logistica, gerente_compras],
        name="SupplyChainTeam",
        description="Equipe de análise e recomendação de compras usando Google Gemini",
        model=decision_llm,  # 🎯 Pro para coordenação do team (evita fallback OpenAI)
    )
    
    print("✅ Supply Chain Team criado com sucesso (4 agentes especializados)")
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
