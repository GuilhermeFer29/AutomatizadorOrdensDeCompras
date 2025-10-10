"""
Agente Conversacional - Orquestrador de chat com NLU e RAG usando Google Gemini.

MIGRAÇÃO COMPLETA PARA GEMINI (2025-10-10):
============================================

✅ MUDANÇAS APLICADAS:
1. Removidas TODAS as dependências OpenAI/OpenRouter (código legado eliminado)
2. Importação centralizada do Gemini via app.agents.llm_config
3. Uso de get_gemini_for_nlu() otimizado para extração de entidades
4. JSON Mode nativo do Gemini para saídas estruturadas
5. Resolução automática de nome de produto para SKU

📋 STACK ATUAL:
- LLM: Google Gemini 1.5 Pro (models/gemini-1.5-pro-latest)
- Framework: Agno 2.1.3
- NLU: Extração de entidades com JSON mode nativo
- RAG: Busca semântica com embeddings Gemini (text-embedding-004)

🎯 FUNCIONALIDADES:
1. Extração de Entidades (NLU): SKU, product_name, intent, quantity
2. Resolução de Contexto: Mantém histórico da sessão
3. RAG: Busca contexto relevante no histórico
4. Routing: Direciona para agentes especializados
5. Fallback Híbrido: Regex + LLM para robustez

REFERÊNCIAS:
- Agno Docs: https://docs.agno.com/
- Gemini API: https://ai.google.dev/gemini-api/docs
- Config LLM: app/agents/llm_config.py
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, Optional
from sqlmodel import Session, select
from app.models.models import Produto, ChatContext
from agno.agent import Agent

# ✅ IMPORTAÇÃO CENTRALIZADA: Configuração otimizada para NLU
from app.agents.llm_config import get_gemini_for_nlu


def resolve_product_name_to_sku(session: Session, product_name: str) -> Optional[str]:
    """
    Resolve o nome do produto para SKU usando busca fuzzy no banco de dados.
    
    Tenta encontrar o produto por:
    1. Correspondência exata (case-insensitive)
    2. Correspondência parcial (LIKE)
    3. Similaridade de texto (se disponível)
    
    Args:
        session: Sessão do banco de dados
        product_name: Nome do produto mencionado pelo usuário
        
    Returns:
        SKU do produto encontrado ou None
    """
    if not product_name or not product_name.strip():
        return None
    
    product_name_clean = product_name.strip().lower()
    
    # 1. Busca exata (case-insensitive)
    from sqlmodel import select, func
    
    produto = session.exec(
        select(Produto).where(
            func.lower(Produto.nome) == product_name_clean
        )
    ).first()
    
    if produto:
        return produto.sku
    
    # 2. Busca parcial com LIKE
    produto = session.exec(
        select(Produto).where(
            func.lower(Produto.nome).contains(product_name_clean)
        )
    ).first()
    
    if produto:
        return produto.sku
    
    # 3. Busca reversa: verifica se o nome do produto contém a palavra-chave
    produtos = session.exec(select(Produto)).all()
    for p in produtos:
        if p.nome and product_name_clean in p.nome.lower():
            return p.sku
    
    return None


def extract_entities_with_llm(message: str, session: Session, session_id: int) -> Dict[str, Any]:
    """
    Extrai entidades usando Gemini Agent com JSON mode nativo.
    
    ✅ ATUALIZAÇÕES (Gemini):
    - Usa get_gemini_for_nlu() otimizado (temperature=0.1 para NLU)
    - JSON mode nativo do Gemini garante saída estruturada
    - Fallback híbrido (LLM + Regex) para robustez máxima
    - Resolução automática de product_name → SKU
    
    Args:
        message: Mensagem do usuário para análise
        session: Sessão do banco de dados
        session_id: ID da sessão de chat
        
    Returns:
        Dict com entidades extraídas: sku, product_name, intent, quantity, confidence
    """
    
    # Carrega contexto da sessão
    context = load_session_context(session, session_id)
    
    # Busca contexto relevante com RAG (embeddings Gemini)
    from app.services.rag_service import get_relevant_context
    rag_context = get_relevant_context(message, session)
    
    # Define as instruções para o agente NLU
    instructions = [
        """Você é um especialista em Natural Language Understanding (NLU) para um sistema de compras industriais.""",
        """Extraia as seguintes entidades da mensagem do usuário:
        - sku: Código do produto (formato SKU_XXX ou null)
        - product_name: Nome do produto mencionado (ou null) - SEMPRE extraia o nome, mesmo que seja informal
        - intent: Intenção do usuário [forecast, price_check, stock_check, purchase_decision, logistics, general_inquiry]
        - quantity: Quantidade numérica mencionada (ou null)
        - confidence: Seu nível de confiança na extração [high, medium, low]""",
        """REGRAS DE EXTRAÇÃO:
        1. Se o usuário mencionar um nome de produto (ex: "Parafuso M8", "Cabo USB", "Cadeira"), extraia para product_name
        2. Se o usuário mencionar um SKU explícito (ex: "SKU_001", "SKU-123"), extraia para sku
        3. Se ambos forem mencionados, preencha ambos os campos
        4. Se o usuário usar pronomes ("ele", "isso", "aquele produto"), resolva usando o contexto
        5. SEMPRE prefira extrair product_name, pois o sistema resolve automaticamente para SKU""",
        """MAPEAMENTO DE INTENT (palavras-chave):
        - forecast: previsão, demanda, média, histórico, tendência, análise, consumo, vendas, giro
        - price_check: preço, custo, valor, mercado, cotação, quanto custa
        - stock_check: estoque, quantidade, disponível, tem produto
        - purchase_decision: comprar, fazer pedido, ordem de compra, preciso
        - logistics: fornecedor, entrega, prazo, logística, supplier
        - general_inquiry: perguntas genéricas ou não classificáveis acima""",
    ]
    
    # ✅ AGENTE NLU: Gemini otimizado para extração de entidades
    agent = Agent(
        name="EntityExtractor",
        description="Extrator de Entidades NLU usando Google Gemini",
        model=get_gemini_for_nlu(),  # ✅ Configuração centralizada (temp=0.1)
        instructions=instructions,
        use_json_mode=True,  # ✅ JSON mode nativo do Gemini
        markdown=False,  # Saída pura (não-markdown para JSON)
    )
    
    try:
        # Monta a mensagem com contexto
        full_message = f"""Analise a seguinte mensagem e extraia as entidades:

Mensagem do usuário: "{message}"

Contexto da sessão anterior:
{json.dumps(context, ensure_ascii=False, indent=2)}

Informações relevantes do histórico (RAG):
{rag_context or 'Nenhum contexto relevante encontrado'}

Retorne um JSON com as entidades extraídas."""
        
        # Executa o agente - com response_model, retorna dict direto
        response = agent.run(full_message)
        
        # Se response_model estiver configurado, a resposta já é um dict
        if isinstance(response, dict):
            result = response
        elif hasattr(response, 'content'):
            # Fallback: tenta parsear o conteúdo
            try:
                result = json.loads(response.content)
            except (json.JSONDecodeError, AttributeError):
                result = response.content if isinstance(response.content, dict) else {}
        else:
            result = {}
        
        # Fallback para extração por regex se LLM não encontrar SKU
        if not result.get("sku"):
            sku_pattern = r'SKU[_-]?(\w+)'
            sku_match = re.search(sku_pattern, message, re.IGNORECASE)
            if sku_match:
                result["sku"] = f"SKU_{sku_match.group(1)}"
            elif context.get("current_sku"):
                result["sku"] = context.get("current_sku")
        
        # ========================================================================
        # CORREÇÃO CRÍTICA (2025-10-09): Fallback Híbrido
        # ========================================================================
        # Se LLM não extrair product_name ou intent, usa regex (fallback interno)
        
        # 1. Fallback de product_name (se LLM não extraiu)
        if not result.get("product_name"):
            product_name_patterns = [
                # Padrões com dois-pontos
                r"produto[:\s]+(.+?)(?:\?|$)",
                r"estoque\s+(?:do|da|de)?\s*(?:meu\s+)?produto[:\s]+(.+?)(?:\?|$)",
                
                # Padrões sem dois-pontos (mais comum)
                r"(?:demanda|média|histórico|previsão|análise|vendas?)\s+(?:do|da|de|o|a)?\s*produto\s+(.+?)(?:\?|$)",
                r"(?:estoque|preço|custo|valor)\s+(?:do|da|de|o|a)?\s*produto\s+(.+?)(?:\?|$)",
                r"produto\s+(.+?)(?:\?|$)",  # Fallback genérico: "produto XYZ"
            ]
            for pattern in product_name_patterns:
                match = re.search(pattern, message.lower(), re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()
                    if potential_name and len(potential_name) > 2:
                        result["product_name"] = potential_name
                        print(f"✅ LLM fallback extraiu product_name: '{potential_name}'")
                        break
        
        # 2. Fallback de intent (se LLM retornou genérico)
        if result.get("intent") in ["general_inquiry", "unknown", None]:
            message_lower = message.lower()
            
            # Análise de demanda, previsão, histórico, vendas
            if any(word in message_lower for word in [
                "previsão", "demanda", "tendência", "forecast", 
                "média", "historico", "histórico", "vendas", "venda",
                "consumo", "saída", "giro", "análise"
            ]):
                result["intent"] = "forecast"
                print(f"✅ LLM fallback detectou intent: 'forecast' (análise/previsão)")
            
            # Consulta de estoque
            elif any(word in message_lower for word in ["estoque", "quantidade", "disponível", "tem"]):
                result["intent"] = "stock_check"
                print(f"✅ LLM fallback detectou intent: 'stock_check'")
            
            # Verificação de preços
            elif any(word in message_lower for word in ["preço", "custo", "valor", "mercado", "cotação"]):
                result["intent"] = "price_check"
                print(f"✅ LLM fallback detectou intent: 'price_check'")
            
            # Decisão de compra
            elif any(word in message_lower for word in ["comprar", "compra", "pedido", "ordem", "preciso"]):
                result["intent"] = "purchase_decision"
                print(f"✅ LLM fallback detectou intent: 'purchase_decision'")
            
            # Logística e fornecedores
            elif any(word in message_lower for word in ["fornecedor", "supplier", "entrega", "logística", "prazo"]):
                result["intent"] = "logistics"
                print(f"✅ LLM fallback detectou intent: 'logistics'")
        
        # 3. Resolve nome do produto para SKU (se tiver product_name mas não SKU)
        if not result.get("sku") and result.get("product_name"):
            resolved_sku = resolve_product_name_to_sku(session, result["product_name"])
            if resolved_sku:
                result["sku"] = resolved_sku
                result["confidence"] = "high"  # Alta confiança quando encontra por nome
                print(f"✅ Resolvido '{result['product_name']}' → SKU: {resolved_sku}")
        
        # 4. Garante que todos os campos existem
        result.setdefault("sku", None)
        result.setdefault("product_name", None)
        result.setdefault("intent", "general_inquiry")
        result.setdefault("quantity", None)
        result.setdefault("confidence", "medium")
        
        print(f"🔍 DEBUG - Entities após fallback híbrido: {result}")
        
        return result
        
    except Exception as e:
        # Fallback para método antigo se LLM falhar completamente
        print(f"Erro no LLM NLU, usando fallback: {e}")
        return extract_entities_fallback(message, session, session_id)


def extract_entities_fallback(message: str, session: Session, session_id: int) -> Dict[str, Any]:
    """
    Fallback - extração baseada em regras (quando LLM NLU falha).
    
    CORREÇÃO (2025-10-09): Adicionada resolução de nome de produto.
    """
    
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
        # Tenta pegar do contexto
        context = load_session_context(session, session_id)
        entities["sku"] = context.get("current_sku")
    
    # 2. Extração de quantidade
    qty_pattern = r'(\d+)\s*(unidade|unidades|peça|peças|uni)'
    qty_match = re.search(qty_pattern, message, re.IGNORECASE)
    if qty_match:
        entities["quantity"] = int(qty_match.group(1))
    
    # 3. Detecção de intent (sincronizado com fallback híbrido)
    message_lower = message.lower()
    
    # Análise de demanda, previsão, histórico, vendas
    if any(word in message_lower for word in [
        "previsão", "demanda", "tendência", "forecast", 
        "média", "historico", "histórico", "vendas", "venda",
        "consumo", "saída", "giro", "análise"
    ]):
        entities["intent"] = "forecast"
    
    # Consulta de estoque
    elif any(word in message_lower for word in ["estoque", "quantidade", "disponível", "tem"]):
        entities["intent"] = "stock_check"
    
    # Verificação de preços
    elif any(word in message_lower for word in ["preço", "custo", "valor", "mercado", "cotação"]):
        entities["intent"] = "price_check"
    
    # Decisão de compra
    elif any(word in message_lower for word in ["comprar", "compra", "pedido", "ordem", "preciso"]):
        entities["intent"] = "purchase_decision"
    
    # Logística e fornecedores
    elif any(word in message_lower for word in ["fornecedor", "supplier", "entrega", "logística", "prazo"]):
        entities["intent"] = "logistics"
    
    # 4. ✅ CORREÇÃO: Tenta resolver nome de produto se não tiver SKU
    if not entities["sku"]:
        # Remove palavras-chave para extrair possível nome de produto
        product_name_patterns = [
            # Padrões com dois-pontos
            r"produto[:\s]+(.+?)(?:\?|$)",
            r"estoque\s+(?:do|da|de)?\s*(?:meu\s+)?produto[:\s]+(.+?)(?:\?|$)",
            
            # Padrões sem dois-pontos (mais comum)
            r"(?:demanda|média|histórico|previsão|análise|vendas?)\s+(?:do|da|de|o|a)?\s*produto\s+(.+?)(?:\?|$)",
            r"(?:estoque|preço|custo|valor)\s+(?:do|da|de|o|a)?\s*produto\s+(.+?)(?:\?|$)",
            r"produto\s+(.+?)(?:\?|$)",  # Fallback genérico
        ]
        
        for pattern in product_name_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                if potential_name and len(potential_name) > 2:
                    entities["product_name"] = potential_name
                    
                    # Tenta resolver para SKU
                    resolved_sku = resolve_product_name_to_sku(session, potential_name)
                    if resolved_sku:
                        entities["sku"] = resolved_sku
                        entities["confidence"] = "medium"
                        print(f"✅ Fallback resolveu '{potential_name}' → {resolved_sku}")
                    break
    
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
    
    # DEBUG: Log entities para diagnóstico
    print(f"🔍 DEBUG - generate_clarification_message called with entities: {entities}")
    
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
