"""
Team de agentes colaborativos usando Agno + Google Gemini 2.5 para análise e recomendação de compras.

📋 STACK ATUAL:
================================
- LLM: Google Gemini 2.5 Flash / 2.5 Flash-Lite / 2.5 Pro
- Framework: Agno (Agent + Team API)
- Embeddings: Google gemini-embedding-001
- Tools: Funções puras (tools_secure.py)
- Structured Output: output_schema (Pydantic models)

🎯 AGENTES ESPECIALIZADOS:
==========================
1. Analista de Demanda: Previsão e análise de estoque
2. Pesquisador de Mercado: Coleta de preços e inteligência competitiva
3. Analista de Logística: Otimização de fornecedores e custos
4. Gerente de Compras: Síntese e recomendação final

REFERÊNCIAS:
============
- Agno Docs: https://docs.agno.com/
- Agno Structured Output: https://docs.agno.com/input-output/structured-output/agent
- Agno Teams: https://docs.agno.com/teams/building-teams
- Gemini API: https://ai.google.dev/gemini-api/docs
- Config LLM: app/agents/llm_config.py
"""

from __future__ import annotations

import json
import logging

from agno.agent import Agent
from agno.team import Team

# ✅ IMPORTAÇÃO CENTRALIZADA: LLMs otimizados com FALLBACK AUTOMÁTICO para 429
from app.agents.llm_config import (
    get_gemini_with_fallback,  # Para todos os agentes - com fallback automático
)

# ✅ Pydantic models para structured output (output_schema — Agno API)
from app.agents.models import (
    DemandAnalysisOutput,
    LogisticsAnalysisOutput,
    MarketResearchOutput,
    PurchaseRecommendationOutput,
)

# ✅ Prompts externalizados em YAML
from app.agents.prompts import load_prompts

# ✅ Import tools SEGUROS (com validação de tenant)
from app.agents.tools_secure import (
    find_supplier_offers_for_sku,
    get_forecast_tool,
    get_price_forecast_for_sku,
    get_product_info,
    search_market_price,
)

logger = logging.getLogger(__name__)

# Carrega prompts do YAML (cached)
_SC_PROMPTS = load_prompts("supply_chain")
ANALISTA_DEMANDA_PROMPT = _SC_PROMPTS["analista_demanda"]
PESQUISADOR_MERCADO_PROMPT = _SC_PROMPTS["pesquisador_mercado"]
ANALISTA_LOGISTICA_PROMPT = _SC_PROMPTS["analista_logistica"]
GERENTE_COMPRAS_PROMPT = _SC_PROMPTS["gerente_compras"]


def create_supply_chain_team() -> Team:
    """
    Cria e retorna o Team de análise de cadeia de suprimentos.

    Arquitetura:
    - LLM: Google Gemini 2.5 Flash (com fallback automático)
    - Framework: Agno — Agent com output_schema + Team com delegação
    - Tools: Funções Python Puras (tools_secure.py)
    - Output: JSON estruturado via Pydantic models

    Agentes Especializados:
    1. Analista de Demanda (temp=0.2): Previsão e análise de estoque
    2. Pesquisador de Mercado (temp=0.2): Coleta de preços
    3. Analista de Logística (temp=0.2): Otimização de fornecedores
    4. Gerente de Compras (temp=0.1): Decisão final (mais determinístico)

    Returns:
        Team: Equipe configurada e pronta para análise

    Raises:
        ValueError: Se GOOGLE_API_KEY não estiver configurada
    """

    # ✅ CONFIGURAÇÃO OTIMIZADA COM FALLBACK: Modelos alternam automaticamente em caso de 429
    logger.info("Configurando agentes com LLMs otimizados + fallback automático")

    # Usar fallback-enabled models para evitar erros 429
    fast_llm = get_gemini_with_fallback(temperature=0.2)      # Com fallback automático
    decision_llm = get_gemini_with_fallback(temperature=0.1)  # Com fallback automático

    # Lista de ferramentas disponíveis (Funções Puras)
    shared_tools = [
        get_product_info,
        get_forecast_tool,
        search_market_price,
        find_supplier_offers_for_sku,
        get_price_forecast_for_sku
    ]

    # ✅ AGENTE 1: Analista de Demanda (RÁPIDO)
    # Responsável por determinar SE precisamos comprar
    analista_demanda = Agent(
        name="AnalistaDemanda",
        role="Especialista em previsão de demanda e análise de estoque",
        description="Analisa dados de estoque e previsões para determinar necessidade de reposição. Retorna JSON: {need_restock: bool, rationale: str}",
        model=fast_llm,  # ⚡ Flash - processamento rápido de dados estruturados
        instructions=[ANALISTA_DEMANDA_PROMPT],
        tools=shared_tools, # Disponibiliza todas as ferramentas relevantes
    )

    # ✅ AGENTE 2: Pesquisador de Mercado (RÁPIDO)
    # Responsável por encontrar ONDE e POR QUANTO comprar
    pesquisador_mercado = Agent(
        name="PesquisadorMercado",
        role="Especialista em inteligência competitiva e análise de preços",
        description="Pesquisa ofertas de fornecedores e compara preços de mercado. Retorna JSON com market_price e supplier_offers",
        model=fast_llm,  # ⚡ Flash - busca e comparação rápida de ofertas
        instructions=[PESQUISADOR_MERCADO_PROMPT],
        tools=shared_tools,
    )

    # ✅ AGENTE 3: Analista de Logística (RÁPIDO)
    # Responsável por avaliar QUAL fornecedor é melhor (custo total)
    analista_logistica = Agent(
        name="AnalistaLogistica",
        role="Especialista em otimização de cadeia de suprimentos e logística",
        description="Avalia fornecedores por custo total, prazo e confiabilidade. Retorna JSON com selected_offer e analysis_notes",
        model=fast_llm,  # ⚡ Flash - cálculos logísticos rápidos
        instructions=[ANALISTA_LOGISTICA_PROMPT],
        tools=shared_tools,
    )

    # ✅ AGENTE 4: Gerente de Compras (PRECISO)
    # Responsável pela DECISÃO FINAL e síntese
    gerente_compras = Agent(
        name="GerenteCompras",
        role="Responsável pela decisão final de aquisição",
        description="Sintetiza análises e toma decisão final de compra. Retorna JSON com decision, supplier, price, quantity_recommended",
        model=decision_llm,  # 🎯 Pro - raciocínio profundo para decisões críticas
        instructions=[GERENTE_COMPRAS_PROMPT],
    )

    # ✅ COORDENAÇÃO AUTOMÁTICA: Agno Team gerencia delegação entre agentes
    # O Team leader delega para os membros com base em seus roles
    team = Team(
        name="SupplyChainTeam",
        members=[analista_demanda, pesquisador_mercado, analista_logistica, gerente_compras],
        model=decision_llm,  # 🎯 Modelo do leader para coordenação
        instructions="Delegue cada etapa ao agente especializado adequado com base no role de cada membro.",
    )

    logger.info("Supply Chain Team criado com sucesso (4 agentes especializados)")
    return team


# ============================================================================
# FUNÇÕES AUXILIARES PARA PARSING E DETECÇÃO DE ERROS
# ============================================================================

def is_output_rate_limited(output_text: str) -> bool:
    """
    Detecta se o output indica erro de rate limit (429).

    Centraliza a lógica de detecção para evitar divergências.
    """
    from app.agents.gemini_fallback import is_rate_limit_error

    lowered = output_text.lower()

    # Detecção por substrings conhecidas
    rate_limit_indicators = [
        "429", "resource_exhausted", "quota", "too many requests", "rate limit"
    ]

    if any(indicator in lowered for indicator in rate_limit_indicators):
        return True

    # Opcionalmente usa a função centralizada do fallback manager
    return is_rate_limit_error(output_text)


def parse_team_json(output_text: str) -> dict:
    """
    Extrai JSON da resposta do Team de agentes.

    Trata diferentes formatos de resposta:
    - JSON puro
    - JSON em bloco ```json ... ```
    - JSON em bloco ``` ... ```
    - JSON misturado com texto

    Raises:
        ValueError: Se não for possível extrair JSON válido
    """
    import re

    # Debug: log do output para diagnóstico
    logger.debug("Output recebido (%d chars): %.300s...", len(output_text), output_text)

    original_text = output_text

    # Caso 1: Bloco ```json ... ```
    if "```json" in output_text:
        json_part = output_text.split("```json", 1)[1]
        if "```" in json_part:
            json_part = json_part.split("```", 1)[0]
        output_text = json_part.strip()
        logger.debug("JSON extraído de bloco ```json")

    # Caso 2: Bloco ``` ... ``` sem "json"
    elif "```" in output_text:
        for part in output_text.split("```"):
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                output_text = part
                logger.debug("JSON extraído de bloco ```")
                break

    # Tenta parse direto
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as je:
        logger.debug("JSON decode falhou: %s", je)

    # Fallback 1: Regex para JSON completo mais externo
    json_search = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', original_text, re.DOTALL)
    if json_search:
        try:
            result = json.loads(json_search.group(0))
            logger.debug("JSON extraído via regex (padrão completo)")
            return result
        except json.JSONDecodeError:
            pass

    # Fallback 2: Busca padrão mais simples
    json_search = re.search(r'(\{.*\})', original_text, re.DOTALL)
    if json_search:
        try:
            result = json.loads(json_search.group(1))
            logger.debug("JSON extraído via regex (padrão simples)")
            return result
        except json.JSONDecodeError as exc:
            logger.warning("Regex encontrou texto mas não é JSON válido")
            raise ValueError("JSON inválido na resposta") from exc

    logger.warning("Nenhum padrão JSON encontrado no output")
    raise ValueError("JSON não encontrado na resposta")


def run_supply_chain_analysis(inquiry: str, max_retries: int = 3) -> dict:
    """
    Função principal para executar análise de cadeia de suprimentos usando Agno Team.

    Esta função cria a equipe de agentes e executa a análise completa baseada
    na consulta (inquiry) fornecida. O Team coordena automaticamente a execução
    dos agentes especializados.

    FALLBACK AUTOMÁTICO: Em caso de erro 429 (rate limit), alterna para outro modelo.

    Args:
        inquiry: Consulta/pergunta sobre a análise de compra (ex: "Analisar compra do SKU_001")
        max_retries: Número máximo de tentativas com diferentes modelos

    Returns:
        Dicionário com o resultado consolidado da análise

    Example:
        >>> result = run_supply_chain_analysis("Preciso comprar 50 unidades do SKU_001")
        >>> print(result["recommendation"]["decision"])
        'approve'
    """
    import time

    from app.agents.gemini_fallback import get_fallback_manager
    from app.agents.llm_metrics import track_llm_call

    manager = get_fallback_manager()
    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info("Tentativa %d/%d (modelo: %s)", attempt + 1, max_retries, manager.current_model_id)

            # Cria o team (usa o modelo atual do fallback manager)
            team = create_supply_chain_team()

            with track_llm_call(model=manager.current_model_id, agent="SupplyChainTeam"):
                response = team.run(inquiry)

            # Extrai conteúdo da resposta
            if hasattr(response, 'content'):
                output_text = response.content
            else:
                output_text = str(response)

            # ✅ Usa helper centralizado para detectar 429 na resposta
            if is_output_rate_limited(output_text):
                raise Exception(f"429 Rate limit detectado na resposta: {output_text[:200]}")

            # ✅ Usa helper centralizado para parsing de JSON
            result = parse_team_json(output_text)
            logger.info("Análise concluída com sucesso na tentativa %d", attempt + 1)
            return result

        except Exception as e:
            last_error = e
            error_str = str(e)

            # ✅ Usa helper centralizado para detecção de 429
            if is_output_rate_limited(error_str):
                logger.warning("Erro 429 na tentativa %d: %.100s", attempt + 1, error_str)

                # Tentar alternar para próximo modelo
                if manager.switch_to_next_model():
                    logger.info("Alternando para modelo: %s", manager.current_model_id)
                    # Pequeno delay antes de retry
                    time.sleep(2)
                    continue
                else:
                    logger.error("Todos os modelos na chain de fallback esgotaram quota!")
                    break
            else:
                # Erro não relacionado a 429, não faz retry
                logger.error("Erro não-429 na execução do Team: %s", e)
                break

    # Fallback em caso de todas as tentativas falharem
    logger.error("Todas as %d tentativas falharam. Retornando manual_review.", max_retries)
    return {
        "decision": "manual_review",
        "rationale": f"Erro técnico ao processar análise: {str(last_error)}",
        "supplier": None,
        "price": None,
        "currency": "BRL",
        "quantity_recommended": 0,
        "next_steps": ["Verificar logs do sistema", "Aguardar cooldown de rate limit", "Tentar novamente mais tarde"],
        "risk_assessment": "Erro sistêmico - rate limit de API"
    }


def execute_supply_chain_team(sku: str, inquiry_reason: str | None = None) -> dict:
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

    # Carrega dados iniciais do produto usando a nova função (get_product_info)
    try:
        product_info_json = get_product_info(sku)
        product_data = json.loads(product_info_json)

        # Se retornou string de erro do tool
        if isinstance(product_data, str):
             # Tenta ver se é mensagem de erro "não encontrado"
             if "não encontrado" in product_data:
                 product_data = {"sku": sku, "nome": "Desconhecido", "erro": product_data}
    except Exception:
        product_data = {"sku": sku, "nome": "Erro ao carregar", "erro": "Parsing error"}

    # Carrega forecast
    try:
        forecast_json = get_forecast_tool(sku)
        forecast_data = json.loads(forecast_json)
    except Exception:
        forecast_data = {}

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
