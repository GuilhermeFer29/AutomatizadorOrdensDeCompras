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
- Tools: Funções puras (tools.py)

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

from agno.agent import Agent
from agno.team import Team

# ✅ IMPORTAÇÃO CENTRALIZADA: LLMs otimizados com FALLBACK AUTOMÁTICO para 429
from app.agents.llm_config import (
    get_gemini_with_fallback,  # Para todos os agentes - com fallback automático
)

# ✅ Import tools SEGUROS (com validação de tenant)
from app.agents.tools_secure import (
    find_supplier_offers_for_sku,
    get_forecast_tool,
    get_price_forecast_for_sku,
    get_product_info,
    search_market_price,
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
1. **find_supplier_offers_for_sku**: Busca ofertas reais de fornecedores cadastrados
2. **get_price_forecast_for_sku**: Obtém previsões ML de preços futuros
3. **search_market_price**: Scraping de preço atual de mercado (se necessário)

## Diretrizes de Resiliência
1. Se `need_restock` for falso, retorne offers vazio
2. SEMPRE use find_supplier_offers_for_sku primeiro para obter ofertas reais
3. Compare as ofertas encontradas com previsões ML quando disponível
4. Documente qualquer falha ou limitação nos dados coletados

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
    - Tools: Lista de Funções Python Puras (tools.py)
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

    # ✅ CONFIGURAÇÃO OTIMIZADA COM FALLBACK: Modelos alternam automaticamente em caso de 429
    print("🚀 Configurando agentes com LLMs otimizados + fallback automático...")
    print("   - Fallback chain: 2.5-flash -> 2.5-flash-lite -> 3-flash")
    print("   - Em caso de 429, o sistema muda automaticamente de modelo")

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
        description="Especialista em previsão de demanda e análise de estoque",
        model=fast_llm,  # ⚡ Flash - processamento rápido de dados estruturados
        instructions=[ANALISTA_DEMANDA_PROMPT],
        tools=shared_tools, # Disponibiliza todas as ferramentas relevantes
        markdown=True,
    )

    # ✅ AGENTE 2: Pesquisador de Mercado (RÁPIDO)
    # Responsável por encontrar ONDE e POR QUANTO comprar
    pesquisador_mercado = Agent(
        name="PesquisadorMercado",
        description="Especialista em inteligência competitiva e análise de preços",
        model=fast_llm,  # ⚡ Flash - busca e comparação rápida de ofertas
        instructions=[PESQUISADOR_MERCADO_PROMPT],
        tools=shared_tools,
        markdown=True,
    )

    # ✅ AGENTE 3: Analista de Logística (RÁPIDO)
    # Responsável por avaliar QUAL fornecedor é melhor (custo total)
    analista_logistica = Agent(
        name="AnalistaLogistica",
        description="Especialista em otimização de cadeia de suprimentos e logística",
        model=fast_llm,  # ⚡ Flash - cálculos logísticos rápidos
        instructions=[ANALISTA_LOGISTICA_PROMPT],
        tools=shared_tools,
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
    print(f"🔍 DEBUG - Output recebido ({len(output_text)} chars):")
    print(f"   Primeiros 300 chars: {output_text[:300]}...")

    original_text = output_text

    # Caso 1: Bloco ```json ... ```
    if "```json" in output_text:
        json_part = output_text.split("```json", 1)[1]
        if "```" in json_part:
            json_part = json_part.split("```", 1)[0]
        output_text = json_part.strip()
        print("   ✓ JSON extraído de bloco ```json")

    # Caso 2: Bloco ``` ... ``` sem "json"
    elif "```" in output_text:
        for part in output_text.split("```"):
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                output_text = part
                print("   ✓ JSON extraído de bloco ```")
                break

    # Tenta parse direto
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as je:
        print(f"   ⚠️ JSON decode falhou: {je}")

    # Fallback 1: Regex para JSON completo mais externo
    json_search = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', original_text, re.DOTALL)
    if json_search:
        try:
            result = json.loads(json_search.group(0))
            print("   ✓ JSON extraído via regex (padrão completo)")
            return result
        except json.JSONDecodeError:
            pass

    # Fallback 2: Busca padrão mais simples
    json_search = re.search(r'(\{.*\})', original_text, re.DOTALL)
    if json_search:
        try:
            result = json.loads(json_search.group(1))
            print("   ✓ JSON extraído via regex (padrão simples)")
            return result
        except json.JSONDecodeError as exc:
            print("   ❌ Regex encontrou texto mas não é JSON válido")
            raise ValueError("JSON inválido na resposta") from exc

    print("   ❌ Nenhum padrão JSON encontrado no output")
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

    manager = get_fallback_manager()
    last_error = None

    for attempt in range(max_retries):
        try:
            print(f"🔄 Tentativa {attempt + 1}/{max_retries} (modelo: {manager.current_model_id})")

            # Cria o team (usa o modelo atual do fallback manager)
            team = create_supply_chain_team()
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
            print(f"✅ Análise concluída com sucesso na tentativa {attempt + 1}")
            return result

        except Exception as e:
            last_error = e
            error_str = str(e)

            # ✅ Usa helper centralizado para detecção de 429
            if is_output_rate_limited(error_str):
                print(f"⚠️ Erro 429 detectado na tentativa {attempt + 1}: {error_str[:100]}")

                # Tentar alternar para próximo modelo
                if manager.switch_to_next_model():
                    print(f"🔄 Alternando para modelo: {manager.current_model_id}")
                    # Pequeno delay antes de retry
                    time.sleep(2)
                    continue
                else:
                    print("❌ Todos os modelos na chain de fallback esgotaram quota!")
                    break
            else:
                # Erro não relacionado a 429, não faz retry
                print(f"❌ Erro não-429 na execução do Team: {e}")
                break

    # Fallback em caso de todas as tentativas falharem
    print(f"❌ Todas as {max_retries} tentativas falharam. Retornando manual_review.")
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
