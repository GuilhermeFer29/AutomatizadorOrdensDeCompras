import json
import logging

from sqlmodel import Session, select

from app.agents.conversational_agent import (
    extract_entities,
    get_conversational_agent,
    save_session_context,
)
from app.models.models import ChatMessage, ChatSession
from app.services.rag_service import embed_and_store_message

LOGGER = logging.getLogger(__name__)


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
        LOGGER.warning("Erro ao indexar mensagem para RAG", exc_info=e)

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
    LOGGER.debug("Entities extracted", extra={"entities": entities})

    # 3. Salva SKU no contexto se foi identificado
    if entities.get("sku"):
        save_session_context(session, session_id, "current_sku", entities["sku"])

    intent = entities.get("intent", "unknown")
    sku = entities.get("sku")

    # 4. DECISÃO SIMPLIFICADA: Análise completa OU conversa natural

    # Se pede análise/decisão de compra E tem SKU → Dispara agente especialista
    if intent in ["purchase_decision", "forecast", "logistics"] and sku:
        LOGGER.info("Disparando analise especializada", extra={"sku": sku})
        response_content, metadata = handle_supply_chain_analysis(session, session_id, entities)

    # QUALQUER OUTRA PERGUNTA → RAG responde naturalmente
    else:
        LOGGER.info("Usando RAG para conversa natural", extra={"message": message_text[:100]})
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
        LOGGER.info("Agente Conversacional processando pergunta")

        # NOTA: O histórico de conversa é gerenciado automaticamente pelo Agno
        # através de add_history_to_context=True e SqliteDb storage.
        # NÃO devemos injetar histórico manualmente no prompt, pois isso causa
        # erro na API do Gemini: "function call turn comes immediately after a user turn"
        # O Agno já mantém o histórico formatado corretamente para o Gemini.

        # Cria o agente conversacional com contexto da sessão (histórico gerenciado pelo Agno)
        agent = get_conversational_agent(session_id=str(session_id))

        # DEBUG: Mostra ferramentas registradas no agente
        if hasattr(agent, 'tools') and agent.tools:
            tool_names = [getattr(t, 'name', str(t)[:30]) for t in agent.tools]
            LOGGER.debug("Ferramentas do agente", extra={"tools": tool_names})

        # Usa apenas a pergunta do usuário - o Agno adiciona o histórico automaticamente
        full_question = user_question

        # Executa o agente com contexto (ele decide automaticamente se delega ou não)
        LOGGER.debug("Pergunta enviada ao agente")
        LOGGER.debug("Pergunta", extra={"question_preview": full_question[:300]})

        response = agent.run(full_question)

        # Verifica se resposta é válida
        if response is None:
            LOGGER.error("Agente retornou None")
            return (
                "Desculpe, houve um erro ao processar sua pergunta. Por favor, tente novamente ou reformule a pergunta de forma mais simples.",
                {"type": "error", "error": "agent_returned_none"}
            )

        # DEBUG: Verifica status da resposta
        if hasattr(response, 'status'):
            LOGGER.debug("Status da resposta: %s", response.status)
        if hasattr(response, 'is_paused') and response.is_paused:
            LOGGER.debug("Resposta PAUSADA")
        if hasattr(response, 'is_cancelled') and response.is_cancelled:
            LOGGER.debug("Resposta CANCELADA")

        # DEBUG: Verifica detalhes da resposta
        LOGGER.debug("Tipo response: %s", type(response).__name__)
        LOGGER.debug("response.content type: %s", type(response.content).__name__ if hasattr(response, "content") else "N/A")

        # Verifica se há tools executadas
        if hasattr(response, 'tools') and response.tools:
            LOGGER.debug("Tools executadas: %d", len(response.tools))
            for t in response.tools:
                LOGGER.debug("Tool: %s", getattr(t, "tool_name", "unknown"))

        if hasattr(response, 'messages') and response.messages:
            LOGGER.debug("Mensagens do agente: %d", len(response.messages))
            for idx, msg in enumerate(response.messages):
                msg_role = getattr(msg, 'role', 'unknown')
                msg_content = getattr(msg, 'content', None)
                msg_content_preview = str(msg_content)[:200] if msg_content else 'None'
                LOGGER.debug("Message [%d] role=%s", idx, msg_role)

                # Verifica tool_calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    LOGGER.debug("tool_calls: %d", len(msg.tool_calls))
                    for tc in msg.tool_calls:
                        if hasattr(tc, 'function'):
                            LOGGER.debug("tool_call: %s", getattr(tc.function, "name", "unknown"))
                        elif isinstance(tc, dict):
                            LOGGER.debug("tool_call: %s", tc.get("function", {}).get("name", "unknown"))

        # Extrai conteúdo da resposta (Agno RunOutput)
        agent_response = None

        # MÉTODO 1: get_content_as_string() - método oficial do Agno (mais confiável)
        if hasattr(response, 'get_content_as_string'):
            try:
                content_str = response.get_content_as_string()
                if content_str and isinstance(content_str, str) and len(content_str.strip()) > 0:
                    agent_response = content_str
                    LOGGER.debug("Resposta via get_content_as_string()")
            except Exception as e:
                LOGGER.debug("get_content_as_string() falhou", exc_info=e)

        # MÉTODO 2: response.content direto
        if not agent_response:
            if hasattr(response, 'content') and response.content and isinstance(response.content, str) and len(response.content.strip()) > 0:
                agent_response = response.content
                LOGGER.debug("Resposta via response.content")

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
                    LOGGER.debug("Resposta via messages (role=%s)", msg_role_str)
                    break

        # MÉTODO 4: Fallback com mensagem padrão
        if not agent_response:
            agent_response = "Desculpe, não consegui formular uma resposta adequada. Por favor, reformule sua pergunta ou seja mais específico sobre o que deseja saber."
            LOGGER.warning("Nenhum metodo retornou conteudo, usando fallback")

        LOGGER.info("Agente respondeu com %d chars", len(agent_response))

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
        LOGGER.exception("Erro no agente conversacional")
        # traceback replaced by LOGGER.exception
        # Stack trace already captured by LOGGER.exception above

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
