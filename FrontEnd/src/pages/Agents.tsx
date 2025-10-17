import { useState, useEffect, useRef } from 'react';
import { useChat } from '@/hooks/useChat';
import api from '@/services/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, CheckCircle2, AlertCircle, Info } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function Agents() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [inputValue, setInputValue] = useState('');
  const { messages, sendMessage, isConnected } = useChat(sessionId);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Cria ou obtém uma sessão de chat ao carregar o componente
    api.post('/api/chat/sessions').then(response => {
      setSessionId(response.data.id);
    });
  }, []);

  useEffect(() => {
    // Rola para a última mensagem
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = () => {
    if (inputValue.trim()) {
      sendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleActionClick = async (sessionId: number, action: any) => {
    try {
      const response = await api.post(`/api/chat/sessions/${sessionId}/actions`, {
        action_type: action.action_type,
        action_data: action.action_data
      });
      
      // Recarrega mensagens para mostrar confirmação
      if (response.data.status === 'success') {
        // A confirmação já foi adicionada pelo backend
        console.log('Ação executada com sucesso');
      }
    } catch (error) {
      console.error('Erro ao executar ação:', error);
    }
  };

  const formatMessageContent = (content: string) => {
    // Remove ## e ### mas mantém o texto
    return content
      .replace(/^###\s+/gm, '')
      .replace(/^##\s+/gm, '')
      .replace(/^#\s+/gm, '');
  };

  const renderMessageMetadata = (metadata: any, msg: any) => {
    if (!metadata) return null;

    return (
      <div className="mt-2 space-y-2">
        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          {/* Confiança */}
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

          {/* SKU */}
          {metadata.sku && (
            <Badge variant="outline" className="text-xs">
              SKU: {metadata.sku}
            </Badge>
          )}

          {/* Task ID (processamento assíncrono) */}
          {metadata.async && (
            <Badge variant="outline" className="text-xs">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Processando...
            </Badge>
          )}

          {/* Tipo de resposta */}
          {metadata.type && (
            <Badge variant="secondary" className="text-xs">
              {metadata.type}
            </Badge>
          )}
        </div>

        {/* Botões Interativos */}
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
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="p-4 border-b">
        <h2 className="text-xl font-semibold">Chat com Agentes Inteligentes</h2>
        <p className="text-sm text-muted-foreground">
          Converse com a equipe de agentes sobre seus produtos e compras
        </p>
      </div>

      {/* Mensagens */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
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
        ))}
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
  );
}

