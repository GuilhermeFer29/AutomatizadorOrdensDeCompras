"""
Tarefas Celery para execução assíncrona de análises de agentes.

CORREÇÕES APLICADAS:
- Atualizado para usar a nova função run_supply_chain_analysis() da API moderna do Agno
- Mantida compatibilidade com execute_supply_chain_analysis() do agent_service.py
"""

from app.core.celery_app import celery_app
import structlog

LOGGER = structlog.get_logger(__name__)

@celery_app.task(name="execute_agent_analysis", bind=True)
def execute_agent_analysis_task(self, sku: str, session_id: int = None):
    """
    Tarefa Celery para executar análise de cadeia de suprimentos usando Agno Team.
    
    CORREÇÃO: Agora salva o resultado no chat quando terminar.
    
    Esta tarefa delega para agent_service.execute_supply_chain_analysis(),
    que por sua vez usa a nova implementação Agno com API moderna.
    
    Args:
        sku: SKU do produto a ser analisado
        session_id: ID da sessão de chat (opcional, para salvar resultado)
        
    Returns:
        Dict com o resultado da análise completa
    """
    from app.services.agent_service import execute_supply_chain_analysis
    from app.agents.conversational_agent import format_agent_response
    
    LOGGER.info("agents.task.start", sku=sku, session_id=session_id)
    
    try:
        result = execute_supply_chain_analysis(sku=sku)
        LOGGER.info("agents.task.completed", sku=sku, decision=result.get("recommendation", {}).get("decision"))
        
        # ✅ CORREÇÃO: Salva resultado no chat quando terminar
        if session_id:
            try:
                from app.core.database import engine
                from app.services.chat_service import add_chat_message
                from sqlmodel import Session
                
                # Formata resposta para o usuário
                formatted_response = format_agent_response(result, intent="forecast")
                
                # Salva como mensagem do assistente
                with Session(engine) as db_session:
                    message = add_chat_message(
                        db_session, 
                        session_id, 
                        'ai', 
                        formatted_response,
                        metadata={"sku": sku, "task_id": self.request.id, "type": "analysis_result"}
                    )
                    
                LOGGER.info("agents.task.result_saved", sku=sku, session_id=session_id)
                
                # ✅ PUBLICA NO REDIS para notificar a API
                try:
                    from app.services.redis_events import redis_events
                    import json
                    
                    message_data = {
                        "id": message.id,
                        "session_id": message.session_id,
                        "sender": message.sender,
                        "content": message.content,
                        "criado_em": message.criado_em.isoformat(),
                        "metadata": json.loads(message.metadata_json) if message.metadata_json else None
                    }
                    
                    # Usa versão síncrona (Celery não suporta async)
                    redis_events.publish_chat_message_sync(session_id, message_data)
                    LOGGER.info("agents.task.redis_published", sku=sku, session_id=session_id)
                except Exception as redis_error:
                    LOGGER.warning("agents.task.redis_failed", sku=sku, error=str(redis_error))
            except Exception as save_error:
                LOGGER.error("agents.task.save_failed", sku=sku, error=str(save_error))
        
        return result
        
    except Exception as e:
        LOGGER.error("agents.task.failed", sku=sku, error=str(e))
        
        # Salva mensagem de erro no chat
        if session_id:
            try:
                from app.core.database import engine
                from app.services.chat_service import add_chat_message
                from sqlmodel import Session
                
                error_message = (
                    f"❌ Desculpe, ocorreu um erro ao analisar o produto {sku}.\n\n"
                    f"Erro: {str(e)}\n\n"
                    f"Por favor, tente novamente ou consulte outro produto."
                )
                
                with Session(engine) as db_session:
                    add_chat_message(
                        db_session, 
                        session_id, 
                        'ai', 
                        error_message,
                        metadata={"sku": sku, "task_id": self.request.id, "type": "analysis_error"}
                    )
            except Exception as save_error:
                LOGGER.error("agents.task.error_save_failed", sku=sku, error=str(save_error))
        
        raise
