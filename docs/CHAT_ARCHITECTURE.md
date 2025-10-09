# Arquitetura do Chat com Agentes

## 📋 Estrutura Atual

### 1. Modelos de Dados (Database)

```python
# app/models/models.py

ChatSession
├── id (PK)
└── criado_em (timestamp)

ChatMessage
├── id (PK)
├── session_id (FK → ChatSession)
├── sender ('human', 'agent', 'system')
├── content (texto da mensagem)
└── criado_em (timestamp)
```

**Características:**
- ✅ Persistência total do histórico
- ✅ Suporte a múltiplas sessões
- ✅ Timestamps para auditoria
- ⚠️ **Limitação**: Sem metadados (ex: qual agente específico respondeu, confiança da resposta)

---

### 2. Serviços (Business Logic)

```python
# app/services/chat_service.py

get_or_create_chat_session()
├── Cria ou recupera uma sessão de chat
└── Retorna: ChatSession

get_chat_history()
├── Busca todas as mensagens de uma sessão
└── Retorna: List[ChatMessage]

add_chat_message()
├── Salva uma nova mensagem no banco
└── Retorna: ChatMessage

process_user_message() ⚠️ SIMPLIFICADO
├── Adiciona mensagem do usuário
├── Roteamento baseado em palavras-chave
│   ├── "previsão" ou "preço" → Agent Analysis Task
│   ├── "estoque" → Consulta direta ao banco
│   └── Outros → Mensagem de erro
├── Adiciona resposta do agente
└── Retorna: ChatMessage
```

**Status Atual:**
- ✅ Funcional
- ⚠️ **Limitação Crítica**: Roteamento muito básico (if/else)
- ⚠️ Não usa os agentes resilientes que acabamos de criar
- ⚠️ Respostas genéricas, sem contexto real

---

### 3. API Endpoints

```python
# app/routers/api_chat_router.py

POST /api/chat/sessions
└── Cria uma nova sessão de chat

GET /api/chat/sessions/{session_id}/messages
└── Retorna histórico da sessão

POST /api/chat/sessions/{session_id}/messages
└── Envia mensagem e recebe resposta (síncrono)

WebSocket /api/chat/ws/{session_id}
└── Conexão em tempo real para chat
```

**Características:**
- ✅ REST + WebSocket
- ✅ Assíncrono via WebSocket
- ⚠️ Não integrado com os agentes avançados

---

### 4. Frontend

```typescript
// FrontEnd/src/hooks/useChat.ts

useChat(sessionId)
├── Gerencia conexão WebSocket
├── Mantém estado das mensagens
└── Função sendMessage()

// FrontEnd/src/pages/Agents.tsx

Chat UI
├── Lista de mensagens (humano vs agente)
├── Campo de entrada
├── Indicador de conexão
└── Auto-scroll para última mensagem
```

**Características:**
- ✅ Interface limpa e funcional
- ✅ Comunicação em tempo real
- ⚠️ Sem indicadores de "agente pensando"
- ⚠️ Sem exibição de confiança/metadados

---

## ⚠️ Problemas Atuais

### 1. Roteamento Simplista
```python
# Atual (chat_service.py)
if "previsão" in message_text.lower():
    # Roteamento manual
```

**Problema**: Não escala. Precisa de um orquestrador inteligente.

### 2. Desconexão dos Agentes Resilientes
O chat atual **não usa** os agentes que acabamos de melhorar:
- ❌ Não chama `execute_supply_chain_analysis()`
- ❌ Não aproveita as novas ferramentas (Tavily, Wikipedia, Python REPL)
- ❌ Não recebe respostas estruturadas com confiança/riscos

### 3. Falta de Contexto
- Sem memória entre mensagens
- Sem extração de entidades (SKU, produto, fornecedor)
- Sem personalização por usuário

---

## 🚀 Arquitetura Proposta (Upgrade)

### Fase 1: Integrar Agentes Resilientes

```python
# app/services/chat_service.py (NOVO)

def process_user_message_v2(session, session_id, message_text):
    # 1. Adiciona mensagem do usuário
    add_chat_message(session, session_id, 'human', message_text)
    
    # 2. EXTRAÇÃO DE ENTIDADES
    entities = extract_entities(message_text)
    # → sku: "SKU_001"
    # → intent: "forecast" | "price" | "stock"
    
    # 3. DISPARA AGENTE CORRETO (assíncrono)
    if entities['intent'] == 'forecast':
        task = execute_agent_analysis_task.delay(
            sku=entities['sku']
        )
        # 4. Resposta imediata com task_id
        response = {
            "content": f"Analisando {entities['sku']}...",
            "task_id": task.id,
            "agent": "supply_chain",
            "status": "processing"
        }
    
    # 5. WEBHOOK/WEBSOCKET para atualizar quando task completar
    return add_chat_message(session, session_id, 'agent', response)
```

### Fase 2: Agente Conversacional (NLU)

```python
# app/agents/conversational_agent.py (NOVO)

ConversationalAgent
├── Entende linguagem natural
├── Extrai SKU, produto, intenção
├── Roteia para agente especialista correto
│   ├── Analista de Demanda
│   ├── Pesquisador de Mercado
│   ├── Analista de Logística
│   └── Gerente de Compras
└── Consolida respostas em linguagem natural
```

**Exemplo de Fluxo:**
```
Humano: "O produto SKU_001 está com estoque baixo?"
    ↓
ConversationalAgent:
    → Extrai: sku="SKU_001", intent="check_stock"
    → Roteia para: AnalistaDemanda
    ↓
AnalistaDemanda (com ferramentas):
    → lookup_product(sku="SKU_001")
    → load_demand_forecast(sku="SKU_001")
    → python_repl_ast: calcula tendência
    → Retorna: {"need_restock": true, "confidence": "high"}
    ↓
ConversationalAgent:
    → Traduz para: "Sim, o SKU_001 está abaixo do mínimo. 
       Baseado na tendência, recomendo reposição em 3 dias."
```

### Fase 3: Memória e Contexto

```python
# app/models/models.py (ADICIONAR)

class ChatContext(SQLModel, table=True):
    session_id: int (FK)
    key: str  # "current_sku", "last_agent_used"
    value: str
    updated_at: datetime
```

**Benefício**: 
```
Humano: "Me mostre o SKU_001"
Agente: [mostra dados]
Humano: "E o preço dele no mercado?"  ← Contexto: sabe que "dele" = SKU_001
```

---

## 📊 Comparação: Antes vs Depois

| Aspecto | Atual | Proposto |
|---------|-------|----------|
| **Roteamento** | If/else manual | Agente NLU |
| **Agentes** | Não integrado | Todos os 4 agentes |
| **Ferramentas** | Nenhuma | Tavily, Wikipedia, Python |
| **Contexto** | Zero | Memória persistente |
| **Confiança** | Não | Sim (high/medium/low) |
| **Assíncrono** | Parcial | Total (Celery) |

---

## 🛠️ Próximas Ações Recomendadas

### Curto Prazo (Essencial)
1. ✅ Criar `conversational_agent.py` com roteamento inteligente
2. ✅ Integrar `execute_supply_chain_analysis()` no chat
3. ✅ Adicionar extração de SKU da mensagem

### Médio Prazo (Importante)
4. ⏳ Implementar `ChatContext` para memória
5. ⏳ Adicionar indicadores de "agente pensando" no frontend
6. ⏳ Exibir confiança e metadados das respostas

### Longo Prazo (Opcional)
7. 🔮 Fine-tuning de modelo para extração de entidades
8. 🔮 Multi-agente com votação (quando há conflito)
9. 🔮 Dashboard de performance dos agentes

---

## 📝 Exemplo de Conversa (Visão Futura)

```
👤 Humano: "Preciso comprar parafusos M8"

🤖 Agente Conversacional:
   "Entendido. Vou analisar:"
   [Dispara: AnalistaDemanda + PesquisadorMercado]

🤖 Analista de Demanda:
   ✓ Estoque atual: 150 unidades
   ✓ Previsão: -50 unid/semana
   ✓ Recomendação: Repor em 2 semanas
   [Confiança: Alta]

🤖 Pesquisador de Mercado:
   ✓ Mercado Livre: R$ 0.15/unid
   ✓ Tavily: Tendência de alta (15%)
   ✓ Wikipedia: Aço inox = melhor custo-benefício
   [Confiança: Média - preço volátil]

🤖 Agente Conversacional (resposta final):
   "Com base na análise:
   - Você tem 3 semanas de estoque
   - Preço atual: R$ 0.15/unid (tendência de alta)
   - Recomendo: Comprar 500 unidades AGORA
   - Economia estimada: R$ 11,25 (se comprar antes da alta)"
   
   [Aprovar] [Detalhes] [Ajustar Quantidade]
```

---

## 🔗 Arquivos Relacionados

- `app/services/chat_service.py` - Lógica atual (a melhorar)
- `app/routers/api_chat_router.py` - Endpoints
- `app/models/models.py` - Estrutura de dados
- `app/agents/supply_chain_graph.py` - Agentes resilientes
- `FrontEnd/src/pages/Agents.tsx` - Interface do chat
