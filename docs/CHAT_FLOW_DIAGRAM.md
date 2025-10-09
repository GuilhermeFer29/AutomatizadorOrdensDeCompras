# Diagrama de Fluxo - Chat com Agentes

## 🔄 Fluxo Atual (Simplificado)

```
┌─────────────┐
│   Frontend  │
│  (React UI) │
└──────┬──────┘
       │ WebSocket
       │ ws://localhost:8000/api/chat/ws/{session_id}
       ↓
┌──────────────────────────────────┐
│   Backend - API Router           │
│  /api/chat/ws/{session_id}       │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│   chat_service.py                │
│  process_user_message()          │
│                                  │
│  ⚠️ ROTEAMENTO SIMPLES:         │
│  if "previsão" in msg:           │
│     → execute_agent_task()       │
│  elif "estoque" in msg:          │
│     → query database             │
│  else:                           │
│     → erro genérico              │
└──────┬───────────────────────────┘
       │
       ↓
┌──────────────────────────────────┐
│   Database (MySQL)               │
│   ├─ chat_sessions              │
│   └─ chat_messages              │
└──────────────────────────────────┘
```

**Problemas:**
- ❌ Não usa os agentes resilientes
- ❌ Roteamento manual (if/else)
- ❌ Sem contexto entre mensagens

---

## 🚀 Fluxo Proposto (Com Agentes Resilientes)

```
┌─────────────┐
│   Frontend  │
│  (React UI) │
└──────┬──────┘
       │ WebSocket
       ↓
┌────────────────────────────────────────────────────┐
│   Backend - API Router                             │
│  /api/chat/ws/{session_id}                         │
└──────┬─────────────────────────────────────────────┘
       │
       ↓
┌────────────────────────────────────────────────────┐
│   Agente Conversacional (NOVO)                     │
│   conversational_agent.py                          │
│                                                    │
│   1. Entende linguagem natural                     │
│   2. Extrai entidades:                             │
│      - SKU                                         │
│      - Intent (forecast/price/stock/purchase)      │
│      - Contexto da sessão                          │
│   3. Roteia para agente especialista               │
└──────┬─────────────────────────────────────────────┘
       │
       ├─────────────┬──────────────┬──────────────┬─────────────┐
       ↓             ↓              ↓              ↓             ↓
┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌──────────┐
│  Analista   │ │Pesquisador│ │ Analista │ │  Gerente    │ │ Outros   │
│ de Demanda  │ │de Mercado│ │Logística │ │ de Compras  │ │ Serviços │
│             │ │          │ │          │ │             │ │          │
│ Tools:      │ │Tools:    │ │Tools:    │ │Tools:       │ │          │
│ • lookup    │ │• scrape  │ │• distance│ │• python     │ │          │
│ • forecast  │ │• tavily  │ │• python  │ │             │ │          │
│ • python    │ │• wiki    │ │          │ │             │ │          │
└─────┬───────┘ └────┬─────┘ └────┬─────┘ └──────┬──────┘ └────┬─────┘
      │              │            │               │             │
      └──────────────┴────────────┴───────────────┴─────────────┘
                                  │
                                  ↓
                    ┌──────────────────────────┐
                    │  Celery Worker           │
                    │  (Processamento Async)   │
                    └────────────┬─────────────┘
                                 │
                                 ↓
                    ┌──────────────────────────┐
                    │  Resultado Consolidado   │
                    │  {                       │
                    │    decision: "approve",  │
                    │    confidence: "high",   │
                    │    rationale: "...",     │
                    │    next_steps: [...]     │
                    │  }                       │
                    └────────────┬─────────────┘
                                 │
                                 ↓
                    ┌──────────────────────────┐
                    │  Database                │
                    │  ├─ chat_sessions        │
                    │  ├─ chat_messages        │
                    │  ├─ chat_context (NOVO)  │
                    │  └─ agent_executions     │
                    └──────────────────────────┘
```

---

## 📝 Exemplo de Execução Detalhado

### Cenário: "Preciso comprar mais SKU_001?"

```
PASSO 1 - Frontend envia mensagem
┌─────────────────────────────────────┐
│ WebSocket.send("Preciso comprar     │
│ mais SKU_001?")                     │
└─────────────────────────────────────┘
          ↓

PASSO 2 - Agente Conversacional processa
┌─────────────────────────────────────┐
│ conversational_agent.py             │
│                                     │
│ extract_entities(message):          │
│   - sku: "SKU_001"                  │
│   - intent: "purchase_decision"     │
│   - context: session_history        │
└─────────────────────────────────────┘
          ↓

PASSO 3 - Dispara Supply Chain Analysis
┌─────────────────────────────────────┐
│ Celery Task (Assíncrono)            │
│ execute_supply_chain_analysis(      │
│   sku="SKU_001"                     │
│ )                                   │
└─────────────────────────────────────┘
          ↓
┌─────────────────────────────────────┐
│ GRAFO DE AGENTES                    │
│                                     │
│ ┌─────────────────┐                │
│ │AnalistaDemanda  │                │
│ │ ✓ lookup_product│                │
│ │ ✓ forecast      │                │
│ │ → need_restock=T│                │
│ └────────┬────────┘                │
│          ↓                          │
│ ┌─────────────────┐                │
│ │PesquisadorMercad│                │
│ │ ✓ scrape_price  │                │
│ │ ✓ tavily_search │                │
│ │ → offers=[...]  │                │
│ └────────┬────────┘                │
│          ↓                          │
│ ┌─────────────────┐                │
│ │AnalistaLogística│                │
│ │ ✓ compute_dist  │                │
│ │ → selected_offer│                │
│ └────────┬────────┘                │
│          ↓                          │
│ ┌─────────────────┐                │
│ │GerenteCompras   │                │
│ │ → decision      │                │
│ └─────────────────┘                │
└─────────────────────────────────────┘
          ↓

PASSO 4 - Callback quando task completa
┌─────────────────────────────────────┐
│ WebSocket.send_json({               │
│   "sender": "agent",                │
│   "content": "Sim, recomendo        │
│      comprar 500 unidades...",      │
│   "metadata": {                     │
│     "confidence": "high",           │
│     "decision": "approve",          │
│     "supplier": "Fornecedor X"      │
│   }                                 │
│ })                                  │
└─────────────────────────────────────┘
          ↓

PASSO 5 - Frontend exibe resposta
┌─────────────────────────────────────┐
│ [Agente] Sim, recomendo comprar    │
│ 500 unidades do SKU_001.            │
│                                     │
│ 💡 Confiança: Alta                  │
│ 📊 [Ver Análise Completa]           │
│ ✅ [Aprovar Compra]                 │
└─────────────────────────────────────┘
```

---

## 🔧 Componentes que Precisam ser Criados

### 1. Agente Conversacional
```python
# app/agents/conversational_agent.py (NOVO)

def extract_entities(message: str, session_context: dict):
    """Extrai SKU, intent, produto da mensagem."""
    pass

def route_to_specialist(intent: str, entities: dict):
    """Decide qual agente especialista chamar."""
    pass

def format_response(agent_output: dict):
    """Traduz resposta técnica para linguagem natural."""
    pass
```

### 2. Modelo de Contexto
```python
# app/models/models.py (ADICIONAR)

class ChatContext(SQLModel, table=True):
    session_id: int
    key: str
    value: str
    updated_at: datetime
```

### 3. Serviço Aprimorado
```python
# app/services/chat_service.py (MELHORAR)

def process_user_message_v2(session, session_id, message_text):
    # 1. Carregar contexto da sessão
    context = load_session_context(session, session_id)
    
    # 2. Extrair entidades
    entities = extract_entities(message_text, context)
    
    # 3. Chamar agente especialista (assíncrono)
    task = dispatch_to_agent(entities)
    
    # 4. Salvar contexto atualizado
    save_session_context(session, session_id, entities)
    
    # 5. Retornar resposta imediata
    return {
        "content": "Analisando...",
        "task_id": task.id
    }
```

### 4. Callback para Tarefas Concluídas
```python
# app/tasks/agent_tasks.py (ADICIONAR)

@celery_app.task
def notify_chat_completion(task_id, session_id, result):
    """Notifica via WebSocket quando análise completa."""
    # Envia pelo WebSocket para session_id
    pass
```

---

## 📦 Resumo das Camadas

```
┌────────────────────────────────────┐
│        Frontend (React)            │  Interface do usuário
├────────────────────────────────────┤
│        API Router (FastAPI)        │  Endpoints REST/WebSocket
├────────────────────────────────────┤
│   Conversational Agent (NOVO)      │  NLU + Roteamento
├────────────────────────────────────┤
│   Specialist Agents (4 agentes)    │  Análises especializadas
├────────────────────────────────────┤
│   Tools (Tavily, Wiki, Python)     │  Ferramentas externas
├────────────────────────────────────┤
│   Celery Workers                   │  Processamento assíncrono
├────────────────────────────────────┤
│   Database (MySQL)                 │  Persistência
└────────────────────────────────────┘
```
