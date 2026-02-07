import { useState, useEffect, useRef } from 'react';
import { ChatMessage } from '@/types/api.types';
import api from '@/services/api';

/**
 * Build the WebSocket URL dynamically from the API base URL env var
 * or fall back to the current page origin.
 */
function buildWsUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (base) {
    // Replace http(s):// with ws(s)://
    return base.replace(/^http/, 'ws') + path;
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}${path}`;
}

export const useChat = (sessionId: number | null) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [hasAsyncTask, setHasAsyncTask] = useState(false);
  const websocket = useRef<WebSocket | null>(null);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    // Fetch initial history
    api.get(`/api/chat/sessions/${sessionId}/messages`).then(response => {
      setMessages(response.data);
      
      // Verifica se há task assíncrona em andamento
      const hasAsync = response.data.some((msg: ChatMessage) => 
        msg.metadata?.async === true || msg.metadata?.type === 'analysis_started'
      );
      setHasAsyncTask(hasAsync);
    });

    // Setup WebSocket with dynamic URL and JWT auth token
    const token = localStorage.getItem('token');
    const wsPath = `/api/chat/ws/${sessionId}${token ? `?token=${token}` : ''}`;
    const ws = new WebSocket(buildWsUrl(wsPath));
    websocket.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setMessages(prevMessages => [...prevMessages, message]);
      
      // Ativa polling se for uma task assíncrona
      if (message.metadata?.async === true || message.metadata?.type === 'analysis_started') {
        setHasAsyncTask(true);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    return () => {
      ws.close();
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
    };
  }, [sessionId]);

  // ✅ CORREÇÃO: Polling para buscar resultado de tasks assíncronas
  useEffect(() => {
    if (!sessionId || !hasAsyncTask) return;

    console.log('🔄 Iniciando polling para task assíncrona...');

    const pollMessages = async () => {
      try {
        const response = await api.get(`/api/chat/sessions/${sessionId}/messages`);
        const newMessages = response.data;
        
        // Verifica se há nova mensagem de resultado
        const hasResult = newMessages.some((msg: ChatMessage) => 
          msg.metadata?.type === 'analysis_result' || msg.metadata?.type === 'analysis_error'
        );
        
        if (hasResult) {
          console.log('✅ Resultado da análise recebido!');
          setMessages(newMessages);
          setHasAsyncTask(false); // Para o polling
          
          if (pollingInterval.current) {
            clearInterval(pollingInterval.current);
            pollingInterval.current = null;
          }
        } else {
          // Atualiza mensagens sem parar o polling
          setMessages(newMessages);
        }
      } catch (error) {
        console.error('Erro ao buscar mensagens:', error);
      }
    };

    // Faz polling a cada 2 segundos (mais responsivo)
    pollingInterval.current = setInterval(pollMessages, 2000);

    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
        pollingInterval.current = null;
      }
    };
  }, [sessionId, hasAsyncTask]);

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
