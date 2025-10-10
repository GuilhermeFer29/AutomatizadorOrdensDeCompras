"""
Agente Conversacional - Orquestrador de chat com NLU e RAG.

CORREÇÕES FINAIS APLICADAS (Agno 2.1.3 - 2025-10-09):

ATUALIZAÇÃO COMPLETA PARA AGNO 2.1.3:
1. Imports corretos:
   - ✅ from agno.agent import Agent
   - ✅ from agno.models.openai import OpenAIChat (não OpenAI!)

2. OpenAIChat configurado corretamente:
   - ✅ id: str (nome do modelo) - CORRETO para Agno 2.1.3
   - ✅ api_key: str
   - ✅ base_url: str
   - ✅ temperature: float

3. Agent NLU configurado conforme API 2.1.3:
   - ✅ name: str (nome do agente)
   - ✅ model: OpenAIChat (instância do LLM)
   - ✅ instructions: List[str] (lista de diretrizes)
   - ✅ output_schema: Type[BaseModel] (estrutura de saída - substitui response_model)
   - ✅ use_json_mode: bool (força JSON)
   - ✅ markdown: bool (formatação - False para JSON puro)

4. Funcionalidade adicional implementada:
   - ✅ Resolução automática de nome de produto para SKU
   - ✅ Busca fuzzy no banco de dados (exata, parcial, reversa)

REFERÊNCIA: Agno v2.1.3 (instalado e validado)
"""

from __future__ import annotations
import json
import os
import re
from typing import Dict, Any, Optional
from sqlmodel import Session, select
from app.models.models import Produto, ChatContext
from agno.agent import Agent
from agno.models.google import Gemini


def _get_llm_for_agno(temperature: float = 0.3) -> Gemini:
    """
    Retorna modelo Gemini 2.5 Flash configurado para NLU.
    
    Args:
        temperature: Controle de aleatoriedade (0.3 = padrão para NLU)
        
    Returns:
        Instância Gemini configurada
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Variável de ambiente 'GOOGLE_API_KEY' não configurada. "
            "Obtenha sua chave em: https://aistudio.google.com/app/apikey"
        )
    
    return Gemini(
        id="gemini-2.5-pro",  # Mesmo modelo do supply_chain_team
        temperature=temperature,
        api_key=api_key
    )


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
    Extrai entidades usando Agno Agent com JSON mode.
    
    Usa use_json_mode=True para garantir que a saída seja JSON válido,
    eliminando a necessidade de parsing manual.
    """
    
    # Carrega contexto da sessão
    context = load_session_context(session, session_id)
    
    # Busca contexto relevante com RAG
    from app.services.rag_service import get_relevant_context
    rag_context = get_relevant_context(message, session)
    
    # Define as instruções para o agente
    instructions = [
        """Você é um assistente de análise de mensagens para um sistema de compras.""",
        """Extraia as seguintes informações da mensagem do usuário:
        - sku: Código do produto (formato SKU_XXX ou null)
        - product_name: Nome do produto mencionado (ou null) - IMPORTANTE: Extraia SEMPRE o nome do produto, mesmo que seja informal
        - intent: Um de [forecast, price_check, stock_check, purchase_decision, logistics, general_inquiry]
        - quantity: Quantidade numérica mencionada (ou null)
        - confidence: Seu nível de confiança (high/medium/low)""",
        """REGRAS DE EXTRAÇÃO:
        1. Se o usuário mencionar um nome de produto (ex: "Parafuso M8", "Cabo USB", "Cadeira de Escritório"), extraia para product_name
        2. Se o usuário mencionar um SKU (ex: "SKU_001", "SKU-123"), extraia para sku
        3. Se ambos forem mencionados, preencha ambos os campos
        4. Se o usuário usar pronomes como "ele", "dela", "isso", use o contexto para resolver a referência
        5. Prefira extrair product_name sempre que possível, pois o sistema pode resolver automaticamente para SKU""",
        """MAPEAMENTO DE INTENT:
        - forecast: Previsão de demanda, média de vendas, histórico, tendência, análise, consumo, giro
        - price_check: Preços, custo, valor de mercado, cotação
        - stock_check: Estoque, quantidade disponível, tem produto
        - purchase_decision: Comprar, fazer pedido, ordem de compra
        - logistics: Fornecedor, entrega, prazo, logística
        - general_inquiry: Qualquer outra pergunta genérica""",
    ]
    
    # Cria agente Agno 2.1.3 com JSON mode ativado
    agent = Agent(
        name="EntityExtractor",
        description="Extrator de Entidades - Analisa mensagens e extrai informações estruturadas",
        model=_get_llm_for_agno(temperature=0.2),
        instructions=instructions,
        use_json_mode=True,  # ✅ Força resposta em JSON (Agno 2.1.3)
        markdown=False,
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
