"""
Agente Conversacional - Arquitetura Pura Agno (Modernizada).

Este agente utiliza 100% dos recursos nativos do framework Agno:
✅ KnowledgeBase: Para RAG (ChromaDB + Gemini Embeddings)
✅ Agent Storage: Para persistência de memória (SQLite)
✅ Tools: Funções Python puras para ações
✅ ReasoningTools: Para raciocínio estruturado (Think → Act → Analyze)

MIGRAÇÃO CONCLUÍDA (2025-10-16).
REASONING ADICIONADO (2026-01-14).
"""

from datetime import UTC
import logging

logger = logging.getLogger(__name__)

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.tools.reasoning import ReasoningTools
from sqlmodel import Session

# Importações locais (Nova Arquitetura)
from app.agents.knowledge import load_knowledge_base
from app.agents.llm_config import get_gemini_with_fallback
from app.agents.prompts import load_prompts
from app.agents.tools_secure import (
    create_purchase_order_tool,
    find_supplier_offers_for_sku,
    get_forecast_tool,
    get_price_forecast_for_sku,
    get_product_info,
    list_all_products,
    run_full_purchase_analysis,
    search_market_price,
)

# Carrega prompts do YAML (cached)
_CONV_PROMPTS = load_prompts("conversational")


def get_conversational_agent(session_id: str) -> Agent:
    """
    Cria o Agente Conversacional usando arquitetura Agno Pura.

    Args:
        session_id: ID da sessão para recuperar memória.

    Returns:
        Agent: Instância configurada do Agno Agent.
    """

    # 1. Carregar Base de Conhecimento (RAG)
    # Em produção, isso deve ser um singleton ou carregado globalmente
    knowledge_base = load_knowledge_base()

    # 2. Configurar Storage (Memória Persistente)
    # Salva o histórico de chat em um arquivo SQLite local
    # NOTA: Agno 2.x usa 'db' em vez de 'storage'
    agent_db = SqliteDb(
        db_file="data/agent_memory.db",
        session_table="agent_sessions"
    )

    # 3. Instruções do Agente (carregadas do YAML)
    instructions = _CONV_PROMPTS["conversational_agent"]

    # 4. Instanciar o Agente COM REASONING
    agent = Agent(
        name="PurchaseAssistant",
        model=get_gemini_with_fallback(temperature=0.1), # Gemini with auto-fallback on 429

        # Cérebro & Conhecimento
        instructions=instructions,
        knowledge=knowledge_base, # RAG Nativo!
        search_knowledge=True,    # Ativa busca automática no knowledge

        # Tools & Ações (ReasoningTools primeiro para prioridade)
        tools=[
            ReasoningTools(add_instructions=True),  # think() e analyze()
            list_all_products,       # NOVA: Para perguntas gerais
            get_product_info,
            search_market_price,
            get_forecast_tool,
            get_price_forecast_for_sku,
            find_supplier_offers_for_sku,
            run_full_purchase_analysis,
            create_purchase_order_tool
        ],

        # Memória & Persistência (Agno 2.x usa 'db')
        db=agent_db,
        session_id=session_id, # Recupera contexto anterior
        add_history_to_context=True, # Envia histórico para o LLM
        num_history_messages=5, # Mantém últimas 5 trocas

        # Configuração de Saída
        markdown=True,
    )

    return agent

# --- Funções de Compatibilidade (Shim) para ChatService ---

def save_session_context(session: Session, session_id: int, key: str, value: str):
    """
    Função de compatibilidade: Salva um valor no contexto da sessão (Tabela ChatContext).
    """
    from datetime import datetime

    from sqlmodel import select

    from app.models.models import ChatContext

    # Check if context exists
    context_item = session.exec(
        select(ChatContext).where(ChatContext.session_id == session_id, ChatContext.key == key)
    ).first()

    if context_item:
        context_item.value = str(value)
        context_item.atualizado_em = datetime.now(UTC)
        session.add(context_item)
    else:
        context_item = ChatContext(session_id=session_id, key=key, value=str(value))
        session.add(context_item)

    session.commit()

def extract_entities(message: str, session: Session = None, session_id: int = None) -> dict:
    """
    Função de compatibilidade: Extrai entidades usando LLM leve (Gemini Flash).
    """
    import json

    from agno.agent import Agent

    from app.agents.llm_config import get_gemini_for_fast_agents

    # Agente efêmero apenas para extração de estruturados
    extractor = Agent(
        model=get_gemini_for_fast_agents(),
        instructions="Extraia SKU e Intenção da mensagem. Retorne APENAS JSON válido: {'sku': str|null, 'intent': str}",
        markdown=True,
    )

    try:
        response = extractor.run(f"Analise a mensagem e extraia entidades: '{message}'")
        content = response.content

        # Limpeza básica de markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return json.loads(content)
    except Exception as e:
        logger.warning("Erro na extração de entidades: %s", e)
        return {"sku": None, "intent": "unknown"}


def format_agent_response(result: dict, intent: str = "general") -> str:
    """
    Formata a resposta de análise dos agentes para exibição no chat.

    Args:
        result: Dicionário com resultado da análise (vindo de execute_supply_chain_analysis)
        intent: Tipo de intenção para customizar a formatação

    Returns:
        String formatada em Markdown para exibição
    """
    try:
        sku = result.get("product_sku", "N/A")
        recommendation = result.get("recommendation", {})
        forecast = result.get("forecast", {})
        need_restock = result.get("need_restock", False)

        # Construir resposta formatada
        lines = []

        # Cabeçalho
        lines.append(f"## 📊 Análise Completa - {sku}\n")

        # Recomendação Principal
        if recommendation:
            decision = recommendation.get("decision", "Análise não disponível")
            reasoning = recommendation.get("reasoning", "")

            emoji = "✅" if "comprar" in decision.lower() else "⏳" if "aguardar" in decision.lower() else "ℹ️"
            lines.append(f"### {emoji} Recomendação")
            lines.append(f"**{decision}**\n")
            if reasoning:
                lines.append(f"{reasoning}\n")

        # Status de Estoque
        if need_restock:
            lines.append("### ⚠️ Alerta de Estoque")
            lines.append("Este produto precisa de reposição urgente!\n")

        # Previsão
        if forecast and forecast.get("prices"):
            lines.append("### 📈 Previsão de Preços")
            prices = forecast.get("prices", [])
            dates = forecast.get("dates", [])
            if prices and dates:
                lines.append(f"- Próximo preço previsto: R$ {prices[0]:.2f}")
                lines.append(f"- Tendência: {'📉 Queda' if prices[-1] < prices[0] else '📈 Alta'}\n")

        # Rodapé
        lines.append("---")
        lines.append("*Análise gerada automaticamente pelo sistema de agentes.*")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Erro ao formatar resposta da análise: {str(e)}\n\nDados brutos: {result}"

