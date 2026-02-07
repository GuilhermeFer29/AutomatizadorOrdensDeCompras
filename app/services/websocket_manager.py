"""WebSocket Manager para notificações em tempo real."""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia conexões WebSocket por sessão de chat."""

    def __init__(self):
        # Dict[session_id, Set[WebSocket]]
        self.active_connections: dict[int, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: int):
        """Conecta um novo cliente."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        logger.info(f"WebSocket conectado: session_id={session_id}, total={len(self.active_connections[session_id])}")

    def disconnect(self, websocket: WebSocket, session_id: int):
        """Desconecta um cliente."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # Remove sessão se não tem mais conexões
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

            logger.info(f"WebSocket desconectado: session_id={session_id}")

    async def send_message(self, session_id: int, message: dict):
        """Envia mensagem para todos os clientes de uma sessão."""
        if session_id not in self.active_connections:
            logger.warning(f"Nenhuma conexão ativa para session_id={session_id}")
            return

        # Envia para todos os clientes conectados
        disconnected = set()
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_json(message)
                logger.info(f"Mensagem enviada via WebSocket: session_id={session_id}")
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")
                disconnected.add(connection)

        # Remove conexões que falharam
        for connection in disconnected:
            self.disconnect(connection, session_id)

    async def broadcast_to_session(self, session_id: int, sender: str, content: str, metadata: dict = None):
        """Envia uma mensagem formatada para todos os clientes de uma sessão."""
        from datetime import datetime

        message = {
            "id": int(datetime.now().timestamp() * 1000),  # ID temporário
            "session_id": session_id,
            "sender": sender,
            "content": content,
            "criado_em": datetime.now().isoformat(),
            "metadata": metadata
        }

        await self.send_message(session_id, message)


# Instância global do manager
websocket_manager = ConnectionManager()
