import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.services.chat_service import get_or_create_chat_session, get_chat_history, process_user_message, add_chat_message
from app.services.websocket_manager import websocket_manager
from app.models.models import ChatAction, ChatSession, ChatMessage
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/chat", tags=["api-chat"])

class ChatMessageCreate(BaseModel):
    content: str

class ChatActionExecute(BaseModel):
    action_type: str
    action_data: Dict[str, Any]

@router.get("/sessions")
def list_chat_sessions(
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """Lista todas as sessões de chat com preview da primeira mensagem."""
    from sqlalchemy import func, desc
    
    # Buscar sessões ordenadas por data (mais recentes primeiro)
    chat_sessions = session.exec(
        select(ChatSession)
        .order_by(desc(ChatSession.criado_em))
        .limit(limit)
    ).all()
    
    result = []
    for chat_sess in chat_sessions:
        # Buscar primeira mensagem como preview
        first_message = session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_sess.id)
            .order_by(ChatMessage.criado_em)
            .limit(1)
        ).first()
        
        # Contar total de mensagens
        message_count = session.exec(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.session_id == chat_sess.id)
        ).first() or 0
        
        preview = first_message.content[:80] + "..." if first_message and len(first_message.content) > 80 else (first_message.content if first_message else "Nova conversa")
        
        result.append({
            "id": chat_sess.id,
            "criado_em": chat_sess.criado_em.isoformat(),
            "preview": preview,
            "message_count": message_count
        })
    
    return result

@router.post("/sessions")
def create_chat_session(session: Session = Depends(get_session)):
    return get_or_create_chat_session(session)


@router.delete("/sessions/{session_id}")
def delete_chat_session(session_id: int, session: Session = Depends(get_session)):
    """Deleta uma sessão de chat e todas as suas mensagens."""
    
    # Verificar se a sessão existe
    chat_sess = session.get(ChatSession, session_id)
    if not chat_sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    
    # Deletar todas as mensagens da sessão primeiro
    messages = session.exec(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
    ).all()
    
    for msg in messages:
        session.delete(msg)
    
    # Deletar a sessão
    session.delete(chat_sess)
    session.commit()
    
    return {"message": "Sessão deletada com sucesso"}

@router.get("/sessions/{session_id}/messages")
def read_chat_history(session_id: int, session: Session = Depends(get_session)):
    """Retorna histórico com metadados parseados."""
    messages = get_chat_history(session, session_id)
    
    # Parseia metadata_json para dict
    result = []
    for msg in messages:
        msg_dict = {
            "id": msg.id,
            "session_id": msg.session_id,
            "sender": msg.sender,
            "content": msg.content,
            "criado_em": msg.criado_em.isoformat(),
            "metadata": json.loads(msg.metadata_json) if msg.metadata_json else None
        }
        result.append(msg_dict)
    
    return result

@router.post("/sessions/{session_id}/messages")
def post_chat_message(session_id: int, message: ChatMessageCreate, session: Session = Depends(get_session)):
    """Envia mensagem e retorna resposta com metadados."""
    agent_response = process_user_message(session, session_id, message.content)
    
    return {
        "id": agent_response.id,
        "session_id": agent_response.session_id,
        "sender": agent_response.sender,
        "content": agent_response.content,
        "criado_em": agent_response.criado_em.isoformat(),
        "metadata": json.loads(agent_response.metadata_json) if agent_response.metadata_json else None
    }

@router.post("/sessions/{session_id}/actions")
def execute_chat_action(
    session_id: int,
    action: ChatActionExecute,
    db_session: Session = Depends(get_session)
):
    """Executa uma ação de botão interativo."""
    
    if action.action_type == "approve_purchase":
        # Cria ordem de compra
        from app.services.order_service import create_order
        sku = action.action_data.get("sku")
        quantity = action.action_data.get("quantity", 1)
        
        order = create_order(db_session, {
            "product": sku,
            "quantity": quantity,
            "value": action.action_data.get("price", 0),
            "origin": "Chat - Aprovação Automática"
        })
        
        # Adiciona mensagem de confirmação ao chat
        confirmation_msg = add_chat_message(
            db_session,
            session_id,
            'system',
            f"✅ Ordem de compra #{order.id} criada com sucesso!\n"
            f"Produto: {sku}\n"
            f"Quantidade: {quantity} unidades",
            {"type": "order_created", "order_id": order.id}
        )
        
        return {"status": "success", "message_id": confirmation_msg.id}
    
    elif action.action_type == "view_details":
        # Retorna detalhes completos
        return {"status": "success", "details": action.action_data}
    
    else:
        raise HTTPException(status_code=400, detail="Tipo de ação não suportado")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int, session: Session = Depends(get_session)):
    # ✅ CORREÇÃO: Usa manager para permitir push de mensagens
    await websocket_manager.connect(websocket, session_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Processa a mensagem e obtém uma resposta imediata
            agent_response = process_user_message(session, session_id, data)
            
            # Envia a resposta do agente com metadados parseados
            response_data = {
                "id": agent_response.id,
                "session_id": agent_response.session_id,
                "sender": agent_response.sender,
                "content": agent_response.content,
                "criado_em": agent_response.criado_em.isoformat(),
                "metadata": json.loads(agent_response.metadata_json) if agent_response.metadata_json else None
            }
            await websocket.send_json(response_data)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, session_id)
        print(f"Client disconnected from session {session_id}")
