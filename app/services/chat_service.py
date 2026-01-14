import json
from sqlmodel import Session, select
from app.models.models import ChatSession, ChatMessage
from app.agents.conversational_agent import (
    extract_entities,
    save_session_context,
    get_conversational_agent,
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
        response_content, metadata = handle_natural_conversation(session, session_id, message_text, entities)
    
    # 5. Salva resposta do agente
    agent_response = add_chat_message(
        session, session_id, 'agent', response_content, metadata
    )
    
    return agent_response


def handle_natural_conversation(session: Session, session_id: int, user_question: str, entities: dict) -> tuple[str, dict]:
    """
    Conversa natural usando AGENTE CONVERSACIONAL (Agno) com delegação inteligente.
    
    O agente pode:
    - Responder perguntas simples diretamente (RAG, previsões rápidas)
    - Delegar análises complexas ao time de especialistas
    - Manter contexto da conversa
    - Conversar de forma natural e amigável
    """
    
    try:
        print(f"🤖 Agente Conversacional processando: '{user_question}'")
        
        # NOTA: O histórico de conversa é gerenciado automaticamente pelo Agno
        # através de add_history_to_context=True e SqliteDb storage.
        # NÃO devemos injetar histórico manualmente no prompt, pois isso causa
        # erro na API do Gemini: "function call turn comes immediately after a user turn"
        # O Agno já mantém o histórico formatado corretamente para o Gemini.
        
        # Cria o agente conversacional com contexto da sessão (histórico gerenciado pelo Agno)
        agent = get_conversational_agent(session_id=str(session_id))
        
        # Usa apenas a pergunta do usuário - o Agno adiciona o histórico automaticamente
        full_question = user_question
        
        # Executa o agente com contexto (ele decide automaticamente se delega ou não)
        print(f"🔧 DEBUG - Pergunta completa enviada ao agente:")
        print(f"   {full_question[:300]}...")
        
        response = agent.run(full_question)
        
        # Verifica se resposta é válida
        if response is None:
            print("❌ Agente retornou None - possível erro na API")
            return (
                "Desculpe, houve um erro ao processar sua pergunta. Por favor, tente novamente ou reformule a pergunta de forma mais simples.",
                {"type": "error", "error": "agent_returned_none"}
            )
        
        # DEBUG: Verifica detalhes da resposta
        print(f"🔧 DEBUG - Tipo response: {type(response)}")
        print(f"🔧 DEBUG - response.content: '{response.content if hasattr(response, 'content') else 'N/A'}' (tipo: {type(response.content) if hasattr(response, 'content') else 'N/A'})")
        
        # Verifica se há tools executadas
        if hasattr(response, 'tools') and response.tools:
            print(f"🔧 DEBUG - Tools executadas: {len(response.tools)}")
            for t in response.tools:
                print(f"   - {getattr(t, 'tool_name', 'unknown')}: {str(getattr(t, 'result', ''))[:100]}")
        
        if hasattr(response, 'messages') and response.messages:
            print(f"🔧 DEBUG - Mensagens do agente: {len(response.messages)}")
            for idx, msg in enumerate(response.messages):
                msg_role = getattr(msg, 'role', 'unknown')
                msg_content = getattr(msg, 'content', None)
                msg_content_preview = str(msg_content)[:200] if msg_content else 'None'
                print(f"   [{idx}] role={msg_role}, content={msg_content_preview}")
                
                # Verifica tool_calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"       🔧 tool_calls: {len(msg.tool_calls)}")
                    for tc in msg.tool_calls:
                        if hasattr(tc, 'function'):
                            print(f"          - {getattr(tc.function, 'name', 'unknown')}")
                        elif isinstance(tc, dict):
                            print(f"          - {tc.get('function', {}).get('name', 'unknown')}")
        
        # Extrai conteúdo da resposta (Agno RunOutput)
        agent_response = None
        
        # MÉTODO 1: get_content_as_string() - método oficial do Agno (mais confiável)
        if hasattr(response, 'get_content_as_string'):
            try:
                content_str = response.get_content_as_string()
                if content_str and isinstance(content_str, str) and len(content_str.strip()) > 0:
                    agent_response = content_str
                    print(f"✅ DEBUG - Resposta extraída via get_content_as_string()")
            except Exception as e:
                print(f"⚠️ DEBUG - get_content_as_string() falhou: {e}")
        
        # MÉTODO 2: response.content direto
        if not agent_response:
            if hasattr(response, 'content') and response.content and isinstance(response.content, str) and len(response.content.strip()) > 0:
                agent_response = response.content
                print(f"✅ DEBUG - Resposta extraída de response.content")
        
        # MÉTODO 3: Busca nas mensagens (model/assistant com content texto)
        if not agent_response and hasattr(response, 'messages') and response.messages:
            for msg in reversed(response.messages):
                msg_role = getattr(msg, 'role', None)
                # Converte enum para string se necessário
                if hasattr(msg_role, 'value'):
                    msg_role = msg_role.value
                msg_role_str = str(msg_role).lower() if msg_role else ''
                
                msg_content = getattr(msg, 'content', None)
                
                # Assistant ou model message com conteúdo texto
                if msg_role_str in ['assistant', 'model'] and msg_content and isinstance(msg_content, str) and len(msg_content.strip()) > 0:
                    agent_response = msg_content
                    print(f"✅ DEBUG - Resposta extraída de messages (role={msg_role_str})")
                    break
        
        # MÉTODO 4: Fallback com mensagem padrão
        if not agent_response:
            agent_response = "Desculpe, não consegui formular uma resposta adequada. Por favor, reformule sua pergunta ou seja mais específico sobre o que deseja saber."
            print(f"⚠️ DEBUG - Usando resposta padrão (nenhum método retornou conteúdo)")
        
        print(f"✅ Agente respondeu: {agent_response[:100]}...")
        print(f"🔧 DEBUG - Resposta completa tem {len(agent_response)} chars")
        
        return (
            agent_response,
            {
                "type": "conversational_agent",
                "query": user_question,
                "entities": entities,
                "confidence": "high"
            }
        )
        
    except Exception as e:
        print(f"❌ Erro no agente conversacional: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: mensagem amigável
        return (
            "Desculpe, tive um problema ao processar sua pergunta. "
            "Pode tentar reformular ou ser mais específico sobre o produto que procura?",
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
