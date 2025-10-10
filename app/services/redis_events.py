"""Redis Pub/Sub para notificações em tempo real entre Worker e API."""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, Callable
import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://broker:6379/0")


class RedisEventManager:
    """Gerencia eventos via Redis Pub/Sub."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.listening_task: Optional[asyncio.Task] = None
        self.handlers: Dict[str, Callable] = {}
    
    async def connect(self):
        """Conecta ao Redis."""
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logger.info("✅ Redis conectado com sucesso")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar Redis: {e}")
            raise
    
    async def disconnect(self):
        """Desconecta do Redis."""
        if self.listening_task:
            self.listening_task.cancel()
        
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Redis desconectado")
    
    async def publish_chat_message(self, session_id: int, message_data: Dict[str, Any]):
        """Publica uma nova mensagem de chat."""
        channel = f"chat:session:{session_id}"
        
        try:
            message_json = json.dumps(message_data)
            await self.redis_client.publish(channel, message_json)
            logger.info(f"📤 Mensagem publicada no Redis: {channel}")
        except Exception as e:
            logger.error(f"❌ Erro ao publicar no Redis: {e}")
    
    def publish_chat_message_sync(self, session_id: int, message_data: Dict[str, Any]):
        """Versão síncrona para usar no Worker (Celery)."""
        import redis as sync_redis
        
        try:
            sync_client = sync_redis.from_url(REDIS_URL, decode_responses=True)
            channel = f"chat:session:{session_id}"
            message_json = json.dumps(message_data)
            sync_client.publish(channel, message_json)
            sync_client.close()
            logger.info(f"📤 Mensagem publicada no Redis (sync): {channel}")
        except Exception as e:
            logger.error(f"❌ Erro ao publicar no Redis (sync): {e}")
    
    async def subscribe_chat_sessions(self, handler: Callable[[int, Dict[str, Any]], None]):
        """Escuta mensagens de todas as sessões de chat."""
        try:
            self.pubsub = self.redis_client.pubsub()
            
            # Subscreve ao padrão chat:session:*
            await self.pubsub.psubscribe("chat:session:*")
            logger.info("👂 Escutando mensagens no Redis: chat:session:*")
            
            # Loop de escuta
            async for message in self.pubsub.listen():
                if message['type'] == 'pmessage':
                    try:
                        # Extrai session_id do canal
                        channel = message['channel']
                        session_id = int(channel.split(':')[-1])
                        
                        # Parse da mensagem
                        message_data = json.loads(message['data'])
                        
                        # Chama o handler
                        await handler(session_id, message_data)
                        
                        logger.info(f"📥 Mensagem recebida do Redis: session_id={session_id}")
                    except Exception as e:
                        logger.error(f"❌ Erro ao processar mensagem do Redis: {e}")
        
        except asyncio.CancelledError:
            logger.info("Redis listener cancelado")
        except Exception as e:
            logger.error(f"❌ Erro no Redis listener: {e}")
    
    async def start_listening(self, handler: Callable[[int, Dict[str, Any]], None]):
        """Inicia escuta em background."""
        self.listening_task = asyncio.create_task(self.subscribe_chat_sessions(handler))


# Instância global
redis_events = RedisEventManager()
