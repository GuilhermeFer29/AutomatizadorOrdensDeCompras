import json
from sqlmodel import Session, select
from app.models.models import ChatSession, ChatMessage
from app.agents.conversational_agent import (
    extract_entities,
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
    """
    Processa mensagem do usuário com conversa fluida e natural.
    
    ESTRATÉGIA:
    1. Perguntas sobre produtos → RAG responde diretamente
    2. Solicitação de análise/compra com SKU → Dispara agente especialista
    3. Qualquer outra coisa → RAG tenta responder
    """
    
    # 1. Salva mensagem do usuário
    add_chat_message(session, session_id, 'human', message_text)

    # 2. Extrai entidades (SKU, intent, etc)
    entities = extract_entities(message_text, session, session_id)
    print(f"🔍 DEBUG - Entities: {entities}")
    
    # 3. Salva SKU no contexto se foi identificado
    if entities.get("sku"):
        save_session_context(session, session_id, "current_sku", entities["sku"])
    
    intent = entities.get("intent", "unknown")
    sku = entities.get("sku")
    
    # 4. DECISÃO SIMPLIFICADA: Análise completa OU conversa natural
    
    # Se pede análise/decisão de compra E tem SKU → Dispara agente especialista
    if intent in ["purchase_decision", "forecast", "logistics"] and sku:
        print(f"🚀 Disparando análise especializada para {sku}")
        response_content, metadata = handle_supply_chain_analysis(session, session_id, entities)
    
    # QUALQUER OUTRA PERGUNTA → RAG responde naturalmente
    else:
        print(f"💬 Usando RAG para conversa natural: '{message_text}'")
        response_content, metadata = handle_natural_conversation(session, message_text, entities)
    
    # 5. Salva resposta do agente
    agent_response = add_chat_message(
        session, session_id, 'agent', response_content, metadata
    )
    
    return agent_response


def handle_natural_conversation(session: Session, user_question: str, entities: dict) -> tuple[str, dict]:
    """
    Conversa natural usando sistema HÍBRIDO (RAG + SQL) - responde QUALQUER pergunta sobre produtos.
    
    O sistema híbrido pode responder:
    - Consultas estruturadas: estoque baixo, filtros, agregações (SQL)
    - Consultas semânticas: descrições, comparações, características (RAG)
    - Consultas complexas: combina SQL + RAG para resposta completa
    """
    from app.services.hybrid_query_service import execute_hybrid_query
    
    try:
        print(f"💬 Sistema Híbrido (RAG + SQL) processando: '{user_question}'")
        hybrid_response = execute_hybrid_query(user_question, session)
        
        # Se sistema híbrido respondeu com sucesso
        if hybrid_response and not hybrid_response.startswith("❌"):
            return (
                hybrid_response,
                {
                    "type": "hybrid_conversation",
                    "query": user_question,
                    "entities": entities,
                    "confidence": "high"
                }
            )
        
        # Se não conseguiu responder
        print("⚠️ Sistema híbrido não conseguiu processar a pergunta")
        return (
            "Desculpe, não consegui encontrar informações sobre isso no catálogo. "
            "Pode reformular sua pergunta ou ser mais específico?",
            {
                "type": "hybrid_no_answer",
                "query": user_question,
                "entities": entities
            }
        )
        
    except Exception as e:
        print(f"❌ Erro no sistema híbrido: {e}")
        import traceback
        traceback.print_exc()
        return (
            "Desculpe, ocorreu um erro ao processar sua pergunta. "
            "Por favor, tente novamente ou reformule de outra forma.",
            {
                "type": "hybrid_error",
                "query": user_question,
                "error": str(e)
            }
        )




def handle_supply_chain_analysis(session: Session, session_id: int, entities: dict) -> tuple[str, dict]:
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
