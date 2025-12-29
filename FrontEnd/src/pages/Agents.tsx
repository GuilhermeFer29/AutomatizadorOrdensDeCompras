import { useState, useEffect, useRef } from 'react';
import { useChat } from '@/hooks/useChat';
import { useLocation } from 'react-router-dom';
import api from '@/services/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, CheckCircle2, AlertCircle, Info, Plus, MessageSquare, Clock, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface ChatSessionItem {
  id: number;
  criado_em: string;
  preview: string;
  message_count: number;
}

export default function Agents() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const { messages, sendMessage, isConnected } = useChat(sessionId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Carregar lista de sessões
  const loadSessions = async () => {
    try {
      const response = await api.get('/api/chat/sessions');
      setSessions(response.data);
    } catch (error) {
      console.error('Erro ao carregar sessões:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    // Pré-preencher a mensagem se vindo de um alerta
    if (location.state?.prefillMessage) {
      setInputValue(location.state.prefillMessage);
    }
  }, [location.state?.prefillMessage]);

  useEffect(() => {
    // Rola para a última mensagem
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const createNewSession = async () => {
    try {
      const response = await api.post('/api/chat/sessions');
      setSessionId(response.data.id);
      // Recarregar lista de sessões
      loadSessions();
      return response.data.id;
    } catch (error) {
      console.error('Erro ao criar sessão:', error);
      return null;
    }
  };

  const selectSession = (id: number) => {
    setSessionId(id);
  };

  const deleteSession = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Evita selecionar a sessão ao clicar em deletar

    if (!confirm('Tem certeza que deseja apagar esta conversa?')) return;

    try {
      await api.delete(`/api/chat/sessions/${id}`);
      // Se a sessão deletada era a selecionada, limpa a seleção
      if (sessionId === id) {
        setSessionId(null);
      }
      loadSessions();
    } catch (error) {
      console.error('Erro ao deletar sessão:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    // Se não tem sessão, criar uma nova antes de enviar
    let currentSessionId = sessionId;
    if (!currentSessionId) {
      currentSessionId = await createNewSession();
      if (!currentSessionId) {
        console.error('Falha ao criar sessão');
        return;
      }
    }

    sendMessage(inputValue);
    setInputValue('');
    // Atualizar lista após enviar mensagem
    setTimeout(loadSessions, 1000);
  };

  const handleActionClick = async (sessionId: number, action: any) => {
    try {
      const response = await api.post(`/api/chat/sessions/${sessionId}/actions`, {
        action_type: action.action_type,
        action_data: action.action_data
      });

      if (response.data.status === 'success') {
        console.log('Ação executada com sucesso');
      }
    } catch (error) {
      console.error('Erro ao executar ação:', error);
    }
  };

  const formatMessageContent = (content: string) => {
    return content
      .replace(/^###\s+/gm, '')
      .replace(/^##\s+/gm, '')
      .replace(/^#\s+/gm, '');
  };

  const renderMessageMetadata = (metadata: any, msg: any) => {
    if (!metadata) return null;

    return (
      <div className="mt-2 space-y-2">
        <div className="flex flex-wrap gap-2">
          {metadata.confidence && (
            <Badge
              variant={
                metadata.confidence === 'high' ? 'default' :
                  metadata.confidence === 'medium' ? 'secondary' :
                    'outline'
              }
              className="text-xs"
            >
              {metadata.confidence === 'high' ? (
                <CheckCircle2 className="h-3 w-3 mr-1" />
              ) : metadata.confidence === 'medium' ? (
                <Info className="h-3 w-3 mr-1" />
              ) : (
                <AlertCircle className="h-3 w-3 mr-1" />
              )}
              Confiança: {metadata.confidence}
            </Badge>
          )}

          {metadata.sku && (
            <Badge variant="outline" className="text-xs">
              SKU: {metadata.sku}
            </Badge>
          )}

          {metadata.async && (
            <Badge variant="outline" className="text-xs">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Processando...
            </Badge>
          )}

          {metadata.type && (
            <Badge variant="secondary" className="text-xs">
              {metadata.type}
            </Badge>
          )}
        </div>

        {metadata.actions && metadata.actions.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {metadata.actions.map((action: any, idx: number) => (
              <Button
                key={idx}
                size="sm"
                variant={action.variant || 'default'}
                onClick={() => handleActionClick(msg.session_id, action)}
              >
                {action.label}
              </Button>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-[calc(100vh-120px)]">
      {/* Sidebar - Histórico de Conversas */}
      <div className="w-72 border-r bg-muted/30 flex flex-col">
        <div className="p-4 border-b">
          <Button
            className="w-full gap-2"
            onClick={createNewSession}
          >
            <Plus className="h-4 w-4" />
            Nova Conversa
          </Button>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {loadingSessions ? (
              <div className="flex items-center justify-center p-4">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center p-4 text-sm text-muted-foreground">
                Nenhuma conversa ainda
              </div>
            ) : (
              sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => selectSession(session.id)}
                  className={cn(
                    "w-full text-left p-3 rounded-lg transition-colors",
                    "hover:bg-muted",
                    sessionId === session.id ? "bg-muted border-l-2 border-primary" : ""
                  )}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare className="h-4 w-4 mt-1 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {session.preview}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                        <Clock className="h-3 w-3" />
                        {formatDistanceToNow(new Date(session.criado_em), {
                          addSuffix: true,
                          locale: ptBR
                        })}
                        <span>•</span>
                        <span>{session.message_count} msgs</span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => deleteSession(session.id, e)}
                      className="p-1 hover:bg-destructive/10 rounded text-muted-foreground hover:text-destructive transition-colors"
                      title="Apagar conversa"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Área principal do chat */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b">
          <h2 className="text-xl font-semibold">Chat com Agentes Inteligentes</h2>
          <p className="text-sm text-muted-foreground">
            Converse com a equipe de agentes sobre seus produtos e compras
          </p>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!sessionId ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
              <MessageSquare className="h-16 w-16 mb-4 opacity-30" />
              <h3 className="text-lg font-medium mb-2">Bem-vindo ao Chat com Agentes</h3>
              <p className="max-w-md">
                Digite uma mensagem abaixo para iniciar uma nova conversa,
                ou selecione uma conversa anterior na barra lateral.
              </p>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
              <MessageSquare className="h-16 w-16 mb-4 opacity-30" />
              <h3 className="text-lg font-medium mb-2">Conversa vazia</h3>
              <p className="max-w-md">
                Envie uma mensagem para começar a conversar com os agentes.
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  'flex items-start gap-3',
                  msg.sender === 'human' ? 'justify-end' : 'justify-start'
                )}
              >
                {msg.sender !== 'human' && (
                  <Avatar className="mt-1">
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      🤖
                    </AvatarFallback>
                  </Avatar>
                )}
                <Card
                  className={cn(
                    'max-w-2xl',
                    msg.sender === 'human'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary'
                  )}
                >
                  <CardContent className="p-4">
                    {msg.sender === 'agent' ? (
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            table: ({ node, ...props }) => (
                              <div className="overflow-x-auto my-4">
                                <table className="min-w-full border-collapse border border-border" {...props} />
                              </div>
                            ),
                            thead: ({ node, ...props }) => (
                              <thead className="bg-muted" {...props} />
                            ),
                            th: ({ node, ...props }) => (
                              <th className="border border-border px-4 py-2 text-left font-semibold" {...props} />
                            ),
                            td: ({ node, ...props }) => (
                              <td className="border border-border px-4 py-2" {...props} />
                            ),
                            tr: ({ node, ...props }) => (
                              <tr className="hover:bg-muted/50 transition-colors" {...props} />
                            ),
                            p: ({ node, ...props }) => (
                              <p className="mb-2 leading-relaxed" {...props} />
                            ),
                            ul: ({ node, ...props }) => (
                              <ul className="list-disc list-inside space-y-1 mb-2" {...props} />
                            ),
                            ol: ({ node, ...props }) => (
                              <ol className="list-decimal list-inside space-y-1 mb-2" {...props} />
                            ),
                            strong: ({ node, ...props }) => (
                              <strong className="font-semibold text-foreground" {...props} />
                            ),
                          }}
                        >
                          {formatMessageContent(msg.content)}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                    {msg.sender === 'agent' && renderMessageMetadata(msg.metadata, msg)}
                  </CardContent>
                </Card>
                {msg.sender === 'human' && (
                  <Avatar className="mt-1">
                    <AvatarFallback className="bg-muted">
                      👤
                    </AvatarFallback>
                  </Avatar>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t bg-background">
          <div className="relative max-w-4xl mx-auto">
            <Input
              placeholder={
                isConnected
                  ? 'Digite sua mensagem (ex: "Qual o estoque do SKU_001?")'
                  : 'Conectando...'
              }
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              disabled={!isConnected}
              className="pr-12"
            />
            <Button
              size="icon"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8"
              onClick={handleSendMessage}
              disabled={!isConnected || !inputValue.trim()}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <div className="text-xs text-muted-foreground text-center mt-2">
            {isConnected ? (
              <span className="flex items-center justify-center gap-1">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
                Conectado • Pronto para conversar
              </span>
            ) : (
              'Conectando ao servidor...'
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
