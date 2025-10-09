"""Agente Conversacional - Orquestrador de chat com NLU e RAG."""

from __future__ import annotations
import json
import os
import re
from typing import Dict, Any, Optional
from sqlmodel import Session, select
from app.models.models import Produto, ChatContext
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


def _get_llm():
    """Retorna LLM configurado com OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL_NAME", "mistralai/mistral-small-3.1-24b-instruct:free")
    
    return ChatOpenAI(
        model=model,
        temperature=0.3,
        openai_api_key=api_key,
        base_url=base_url
    )


def extract_entities_with_llm(message: str, session: Session, session_id: int) -> Dict[str, Any]:
    """Extrai entidades usando LLM - mais inteligente e flexível."""
    
    # Carrega contexto da sessão
    context = load_session_context(session, session_id)
    
    # Busca contexto relevante com RAG
    from app.services.rag_service import get_relevant_context
    rag_context = get_relevant_context(message, session)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Você é um assistente de análise de mensagens para um sistema de compras.
        
Extraia as seguintes informações da mensagem do usuário e retorne em JSON:
- sku: Código do produto (formato SKU_XXX ou null)
- product_name: Nome do produto mencionado (ou null)
- intent: Um de [forecast, price_check, stock_check, purchase_decision, logistics, general_inquiry]
- quantity: Quantidade numérica mencionada (ou null)
- confidence: Seu nível de confiança (high/medium/low)

Contexto da sessão anterior:
{context}

Informações relevantes do histórico (RAG):
{rag_context}

IMPORTANTE: Se o usuário usar pronomes como "ele", "dela", "isso", use o contexto para resolver a referência."""),
        ("user", "{message}")
    ])
    
    llm = _get_llm()
    chain = prompt | llm
    
    try:
        response = chain.invoke({
            "message": message,
            "context": json.dumps(context),
            "rag_context": rag_context or "Nenhum contexto relevante encontrado"
        })
        
        # Parse resposta JSON
        result = json.loads(response.content)
        
        # Fallback para extração por regex se LLM falhar
        if not result.get("sku"):
            sku_pattern = r'SKU[_-]?(\w+)'
            sku_match = re.search(sku_pattern, message, re.IGNORECASE)
            if sku_match:
                result["sku"] = f"SKU_{sku_match.group(1)}"
            elif context.get("current_sku"):
                result["sku"] = context.get("current_sku")
        
        return result
        
    except Exception as e:
        # Fallback para método antigo se LLM falhar
        print(f"Erro no LLM NLU, usando fallback: {e}")
        return extract_entities_fallback(message, session, session_id)


def extract_entities_fallback(message: str, session: Session, session_id: int) -> Dict[str, Any]:
    """Fallback - extração baseada em regras (método antigo)."""
    
    entities = {
        "sku": None,
        "product_name": None,
        "intent": "unknown",
        "quantity": None,
        "confidence": "low"
    }
    
    # 1. Extração de SKU
    sku_pattern = r'SKU[_-]?(\w+)'
    sku_match = re.search(sku_pattern, message, re.IGNORECASE)
    if sku_match:
        entities["sku"] = f"SKU_{sku_match.group(1)}"
    else:
        context = load_session_context(session, session_id)
        entities["sku"] = context.get("current_sku")
    
    # 2. Extração de quantidade
    qty_pattern = r'(\d+)\s*(unidade|unidades|peça|peças|uni)'
    qty_match = re.search(qty_pattern, message, re.IGNORECASE)
    if qty_match:
        entities["quantity"] = int(qty_match.group(1))
    
    # 3. Detecção de intent
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["previsão", "demanda", "tendência", "forecast"]):
        entities["intent"] = "forecast"
    elif any(word in message_lower for word in ["preço", "custo", "valor", "mercado"]):
        entities["intent"] = "price_check"
    elif any(word in message_lower for word in ["estoque", "quantidade", "disponível", "tem"]):
        entities["intent"] = "stock_check"
    elif any(word in message_lower for word in ["comprar", "compra", "pedido", "ordem", "preciso"]):
        entities["intent"] = "purchase_decision"
    elif any(word in message_lower for word in ["fornecedor", "supplier", "entrega", "logística"]):
        entities["intent"] = "logistics"
    
    return entities


# Alias para manter compatibilidade
def extract_entities(message: str, session: Session, session_id: int) -> Dict[str, Any]:
    """Extração de entidades - usa LLM quando possível."""
    return extract_entities_with_llm(message, session, session_id)


def load_session_context(session: Session, session_id: int) -> Dict[str, str]:
    """Carrega o contexto armazenado da sessão."""
    contexts = session.exec(
        select(ChatContext).where(ChatContext.session_id == session_id)
    ).all()
    
    return {ctx.key: ctx.value for ctx in contexts}


def save_session_context(session: Session, session_id: int, key: str, value: str):
    """Salva ou atualiza um item de contexto da sessão."""
    from datetime import datetime, timezone
    
    existing = session.exec(
        select(ChatContext)
        .where(ChatContext.session_id == session_id)
        .where(ChatContext.key == key)
    ).first()
    
    if existing:
        existing.value = value
        existing.atualizado_em = datetime.now(timezone.utc)
        session.add(existing)
    else:
        new_context = ChatContext(
            session_id=session_id,
            key=key,
            value=value
        )
        session.add(new_context)
    
    session.commit()


def route_to_specialist(intent: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """Decide qual agente especialista chamar e como."""
    
    routing = {
        "forecast": {
            "agent": "supply_chain_analysis",
            "reason": "Análise de demanda e previsão",
            "async": True,
        },
        "price_check": {
            "agent": "supply_chain_analysis",
            "reason": "Pesquisa de preços de mercado",
            "async": True,
        },
        "stock_check": {
            "agent": "direct_query",
            "reason": "Consulta direta ao banco de dados",
            "async": False,
        },
        "purchase_decision": {
            "agent": "supply_chain_analysis",
            "reason": "Análise completa para decisão de compra",
            "async": True,
        },
        "logistics": {
            "agent": "supply_chain_analysis",
            "reason": "Análise logística e fornecedores",
            "async": True,
        },
        "unknown": {
            "agent": "clarification",
            "reason": "Intent não identificado",
            "async": False,
        }
    }
    
    return routing.get(intent, routing["unknown"])


def format_agent_response(agent_output: Dict[str, Any], intent: str) -> str:
    """Traduz a resposta técnica do agente para linguagem natural."""
    
    # Se for a análise completa da supply chain
    if "recommendation" in agent_output:
        rec = agent_output["recommendation"]
        decision = rec.get("decision", "manual_review")
        
        if decision == "approve":
            return (
                f"✅ **Recomendo aprovar a compra:**\n\n"
                f"📦 Fornecedor: {rec.get('supplier', 'N/A')}\n"
                f"💰 Preço: {rec.get('currency', 'BRL')} {rec.get('price', 0):.2f}\n"
                f"📊 Quantidade: {rec.get('quantity_recommended', 'N/A')} unidades\n\n"
                f"**Justificativa:** {rec.get('rationale', '')}\n\n"
                f"**Próximos passos:**\n"
                + "\n".join(f"- {step}" for step in rec.get("next_steps", []))
            )
        elif decision == "reject":
            return (
                f"❌ **Não recomendo a compra neste momento.**\n\n"
                f"**Motivo:** {rec.get('rationale', 'Dados insuficientes')}"
            )
        else:
            return (
                f"⚠️ **Recomendo revisão manual.**\n\n"
                f"**Análise:** {rec.get('rationale', '')}\n\n"
                f"**Avaliação de Risco:** {rec.get('risk_assessment', 'N/A')}"
            )
    
    # Fallback genérico
    return f"Análise concluída. Resultado: {json.dumps(agent_output, indent=2)}"


def generate_clarification_message(entities: Dict[str, Any]) -> str:
    """Gera mensagem pedindo esclarecimento quando intent não é claro."""
    
    if not entities.get("sku"):
        return (
            "Não consegui identificar qual produto você está mencionando. "
            "Poderia informar o SKU? (ex: SKU_001)"
        )
    
    return (
        "Posso ajudar com:\n"
        "- 📊 Previsão de demanda\n"
        "- 💰 Verificação de preços\n"
        "- 📦 Consulta de estoque\n"
        "- 🛒 Análise de compra\n"
        "- 🚚 Informações logísticas\n\n"
        "O que você gostaria de saber?"
    )
