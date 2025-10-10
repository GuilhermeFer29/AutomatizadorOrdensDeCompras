import json
from sqlmodel import Session, select
from app.models.models import ChatSession, ChatMessage, Produto
from app.agents.conversational_agent import (
    extract_entities,
    route_to_specialist,
    format_agent_response,
    generate_clarification_message,
    save_session_context,
)
from app.services.rag_service import embed_and_store_message


def get_or_create_chat_session(session: Session, session_id: int = None) -> ChatSession:
    if session_id:
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            return chat_session
    
    # Cria uma nova sessão se não existir
    new_session = ChatSession()
    session.add(new_session)
    session.commit()
    session.refresh(new_session)
    return new_session


def get_chat_history(session: Session, session_id: int):
    return session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.criado_em)
    ).all()


def add_chat_message(
    session: Session, 
    session_id: int, 
    sender: str, 
    content: str,
    metadata: dict = None
) -> ChatMessage:
    """Adiciona uma mensagem ao histórico com metadados opcionais e indexa para RAG."""
    message = ChatMessage(
        session_id=session_id,
        sender=sender,
        content=content,
        metadata_json=json.dumps(metadata) if metadata else None
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    
    # Indexa mensagem para busca semântica (RAG)
    try:
        embed_and_store_message(message)
    except Exception as e:
        print(f"Erro ao indexar mensagem para RAG: {e}")
    
    return message


def process_user_message(session: Session, session_id: int, message_text: str):
    """Processa mensagem do usuário com NLU e roteamento inteligente."""
    
    # 1. Salva mensagem do usuário
    add_chat_message(session, session_id, 'human', message_text)

    # 2. Extrai entidades (SKU, intent, etc)
    entities = extract_entities(message_text, session, session_id)
    
    # DEBUG: Log entities extraídas
    print(f"🔍 DEBUG - Entities extraídas: {entities}")
    
    # 3. Salva SKU no contexto se foi identificado
    if entities.get("sku"):
        save_session_context(session, session_id, "current_sku", entities["sku"])
    
    # 4. Roteia para o agente especialista
    routing = route_to_specialist(entities["intent"], entities)
    print(f"🔍 DEBUG - Routing: {routing}")
    
    # 5. Executa baseado no tipo de agente
    if routing["agent"] == "direct_query":
        # Consulta direta ao banco (stock_check)
        response_content, metadata = handle_stock_check(session, entities)
        
    elif routing["agent"] == "clarification":
        # Pede esclarecimento
        response_content = generate_clarification_message(entities)
        metadata = {"type": "clarification", "entities": entities}
        
    elif routing["agent"] == "supply_chain_analysis":
        # Dispara análise completa (assíncrono)
        response_content, metadata = handle_supply_chain_analysis(session, session_id, entities, routing)
    
    else:
        response_content = "Desculpe, não consegui processar sua solicitação."
        metadata = {"type": "error"}
    
    # 6. Salva resposta do agente
    agent_response = add_chat_message(
        session, session_id, 'agent', response_content, metadata
    )
    
    return agent_response


def handle_stock_check(session: Session, entities: dict) -> tuple[str, dict]:
    """Consulta direta de estoque no banco de dados."""
    sku = entities.get("sku")
    
    if not sku:
        return (
            "Por favor, informe o SKU do produto que deseja consultar.",
            {"type": "error", "reason": "missing_sku"}
        )
    
    product = session.exec(
        select(Produto).where(Produto.sku == sku)
    ).first()
    
    if not product:
        return (
            f"Produto {sku} não encontrado no catálogo.",
            {"type": "not_found", "sku": sku}
        )
    
    status = "✅ OK" if product.estoque_atual >= product.estoque_minimo else "⚠️ BAIXO"
    
    response = (
        f"📦 **{product.nome}** (SKU: {sku})\n\n"
        f"Estoque Atual: {product.estoque_atual} unidades\n"
        f"Estoque Mínimo: {product.estoque_minimo} unidades\n"
        f"Status: {status}"
    )
    
    metadata = {
        "type": "stock_check",
        "sku": sku,
        "stock_atual": product.estoque_atual,
        "stock_minimo": product.estoque_minimo,
        "confidence": "high"
    }
    
    return response, metadata


def handle_supply_chain_analysis(session: Session, session_id: int, entities: dict, routing: dict) -> tuple[str, dict]:
    """Dispara análise completa da supply chain de forma assíncrona.
    
    CORREÇÃO: Agora passa session_id para a task salvar o resultado automaticamente.
    """
    sku = entities.get("sku")
    
    if not sku:
        return (
            "Para análises avançadas, preciso saber qual produto. Informe o SKU.",
            {"type": "error", "reason": "missing_sku"}
        )
    
    # ✅ CORREÇÃO: Passa session_id para task salvar resultado
    from app.tasks.agent_tasks import execute_agent_analysis_task
    task = execute_agent_analysis_task.delay(sku=sku, session_id=session_id)
    
    response = (
        f"🔍 Iniciando análise completa para {sku}...\n\n"
        f"Estou consultando:\n"
        f"- Previsão de demanda\n"
        f"- Preços de mercado\n"
        f"- Análise logística\n"
        f"- Recomendação de compra\n\n"
        f"⏱️ Isso pode levar até 2 minutos. Aguarde que responderei em breve!"
    )
    
    metadata = {
        "type": "analysis_started",
        "sku": sku,
        "task_id": task.id,
        "intent": entities["intent"],
        "async": True
    }
    
    return response, metadata
