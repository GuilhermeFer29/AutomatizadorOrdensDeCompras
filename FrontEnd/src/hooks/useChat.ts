import { useState, useEffect, useRef } from 'react';
import { ChatMessage } from '@/types/api.types';
import api from '@/services/api';

export const useChat = (sessionId: number | null) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const websocket = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    // Fetch initial history
    api.get(`/api/chat/sessions/${sessionId}/messages`).then(response => {
      setMessages(response.data);
    });

    // Setup WebSocket
    const ws = new WebSocket(`ws://localhost:8000/api/chat/ws/${sessionId}`);
    websocket.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setMessages(prevMessages => [...prevMessages, message]);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [sessionId]);

  const sendMessage = (content: string) => {
    if (websocket.current && websocket.current.readyState === WebSocket.OPEN) {
      const userMessage: ChatMessage = {
        id: Date.now(),
        session_id: sessionId!,
        sender: 'human',
        content,
        criado_em: new Date().toISOString(),
      };
      setMessages(prevMessages => [...prevMessages, userMessage]);
      websocket.current.send(content);
    }
  };

  return { messages, sendMessage, isConnected };
};
