"""
Agente Conversacional - Arquitetura Pura Agno (Modernizada).

Este agente utiliza 100% dos recursos nativos do framework Agno:
✅ KnowledgeBase: Para RAG (ChromaDB + Gemini Embeddings)
✅ Agent Storage: Para persistência de memória (SQLite)
✅ Tools: Funções Python puras para ações

MIGRAÇÃO CONCLUÍDA (2025-10-16).
"""

from typing import Optional, List
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.google import Gemini
from sqlmodel import Session

# Importações locais (Nova Arquitetura)
from app.agents.knowledge import load_knowledge_base
from app.agents.llm_config import get_gemini_for_decision_making
from app.agents.tools import (
    get_product_info,
    search_market_price,
    get_forecast_tool,
    get_price_forecast_for_sku,
    find_supplier_offers_for_sku,
    run_full_purchase_analysis,
    create_purchase_order_tool
)

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
    
    # 3. Instruções do Agente
    instructions = [
        "Você é o Assistente de Compras Inteligente (Agno Powered).",
        "Sua missão é ajudar gerentes de suprimentos a tomar decisões rápidas e precisas.",
        "",
        "## SUAS CAPACIDADES (USE-AS!):",
        "1. **Knowledge Base (RAG)**: Você tem acesso a todo o catálogo de produtos e seus detalhes técnicos/estoque.",
        "   - Use isso AUTOMATICAMENTE para responder perguntas sobre 'quais produtos', 'descrição de X', etc.",
        "2. **Tools (Ações)**: Você DEVE usar ferramentas para dados em tempo real:",
        "   - `get_product_info`: Para checar estoque atual exato e status de reposição.",
        "   - `get_price_forecast_for_sku`: Para ver se o preço vai subir ou cair.",
        "   - `find_supplier_offers_for_sku`: Para ver quem vende e por quanto.",
        "   - `run_full_purchase_analysis`: Para recomendações complexas ('devo comprar?').",
        "",
        "## REGRAS DE COMPORTAMENTO:",
        "- **Não alucine**: Se não estiver na Knowledge Base ou Tools, diga que não sabe.",
        "- **Seja Proativo**: Se o estoque estiver baixo (veja na info do produto), alerte e sugira reposição.",
        "- **Resposta Rica**: Use Markdown, listas e emojis para facilitar a leitura.",
        "- **Sempre Cite SKUs**: Ao falar de um produto, mencione seu SKU.",
        "",
        "## EXEMPLOS DE FLUXO:",
        "- Usuário: 'Como está o estoque do SKU_001?'",
        "  -> Ação: Chame `get_product_info('SKU_001')`.",
        "  -> Resposta: 'O estoque atual é X. Mínimo é Y. [Análise se precisa repor]'",
        "",
        "- Usuário: 'Qual melhor fornecedor para MDF?'",
        "  -> Ação: Pesquise 'MDF' na Knowledge Base para achar o SKU.",
        "  -> Ação: Chame `find_supplier_offers_for_sku(sku_encontrado)`.",
        "",
        "- Usuário: 'Devo comprar Parafuso Sextavado agora?'",
        "  -> Ação: `run_full_purchase_analysis(sku)`.",
    ]
    
    # 4. Instanciar o Agente
    agent = Agent(
        name="PurchaseAssistant",
        model=get_gemini_for_decision_making(), # Gemini 1.5 Flash/Pro configurado
        
        # Cérebro & Conhecimento
        instructions=instructions,
        knowledge=knowledge_base, # RAG Nativo!
        search_knowledge=True,    # Ativa busca automática no knowledge
        
        # Tools & Ações
        tools=[
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
    from app.models.models import ChatContext
    from datetime import datetime, timezone
    from sqlmodel import select
    
    # Check if context exists
    context_item = session.exec(
        select(ChatContext).where(ChatContext.session_id == session_id, ChatContext.key == key)
    ).first()
    
    if context_item:
        context_item.value = str(value)
        context_item.atualizado_em = datetime.now(timezone.utc)
        session.add(context_item)
    else:
        context_item = ChatContext(session_id=session_id, key=key, value=str(value))
        session.add(context_item)
    
    session.commit()

def extract_entities(message: str, session: Session = None, session_id: int = None) -> dict:
    """
    Função de compatibilidade: Extrai entidades usando LLM leve (Gemini Flash).
    """
    from agno.agent import Agent
    from app.agents.llm_config import get_gemini_for_fast_agents
    import json

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
        print(f"⚠️ Erro na extração de entidades: {e}")
        return {"sku": None, "intent": "unknown"}
