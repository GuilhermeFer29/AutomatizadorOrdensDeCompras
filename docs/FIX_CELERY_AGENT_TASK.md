# 🔧 CORREÇÃO: Tarefa Celery Agent Analysis

**Data:** 2025-10-09 21:35 BRT  
**Status:** ✅ **CORRIGIDO**

---

## 🔴 PROBLEMA

### Erro no Worker
```
KeyError: 'execute_agent_analysis'
```

**Causa:** Tarefa Celery `execute_agent_analysis` **não estava registrada** no worker.

---

## ✅ CORREÇÃO 1: Registrar a Task

### Arquivo: `app/core/celery_app.py`

**Antes (linha 57-60):**
```python
# Import tasks to ensure they are registered with the Celery application.
import app.tasks.debug_tasks  # noqa: E402,F401
import app.tasks.ml_tasks  # noqa: E402,F401
import app.tasks.scraping_tasks  # noqa: E402,F401
```

**Depois:**
```python
# Import tasks to ensure they are registered with the Celery application.
import app.tasks.agent_tasks  # noqa: E402,F401  ← ✅ ADICIONADO
import app.tasks.debug_tasks  # noqa: E402,F401
import app.tasks.ml_tasks  # noqa: E402,F401
import app.tasks.scraping_tasks  # noqa: E402,F401
```

**Resultado:**
```
[tasks]
  . app.tasks.debug.long_running_task
  . app.tasks.ml_tasks.retrain_all_products_task
  . app.tasks.scraping.scrape_all_products
  . app.tasks.scraping.scrape_product
  . execute_agent_analysis  ← ✅ REGISTRADA!
```

---

## ✅ CORREÇÃO 2: Configurar OPENAI_API_KEY

### Arquivo: `docker-compose.yml`

**Problema Secundário:**
```
ERROR OPENAI_API_KEY not set. Please set the OPENAI_API_KEY environment variable
```

**Causa:** Agno 2.1.3 tenta usar `OPENAI_API_KEY` por padrão, mas o sistema usa `OPENROUTER_API_KEY`.

**Solução:** Adicionar alias no `docker-compose.yml`:

```yaml
worker:
  build:
    context: .
    dockerfile: Dockerfile
  env_file:
    - .env
  environment:
    # WORKAROUND: Agno tenta usar OPENAI_API_KEY por padrão
    # Apontamos para OpenRouter que é compatível
    OPENAI_API_KEY: ${OPENROUTER_API_KEY}
    OPENAI_BASE_URL: ${OPENROUTER_API_BASE}
  depends_on:
    db:
      condition: service_healthy
    broker:
      condition: service_healthy
  command: celery -A app.core.celery_app.celery_app worker --loglevel=info
  volumes:
    - ./app:/app/app
    - ./scripts:/app/scripts
    - ./data:/app/data
    - models_data:/models
    - reports_data:/reports
```

---

## 🔄 FLUXO CORRIGIDO

### Pergunta: "Qual a demanda do produto X?"

```
1. Frontend → API
   POST /api/chat/sessions/1/messages
   ↓
2. API: process_user_message()
   - Extrai entities: intent="forecast", sku="84903501"
   - Rota para "supply_chain_analysis"
   ↓
3. API: handle_supply_chain_analysis()
   - Dispara tarefa Celery assíncrona
   - execute_agent_analysis_task.delay(sku="84903501")
   - Retorna: "🔍 Iniciando análise completa..."
   ↓
4. Worker: execute_agent_analysis_task(sku)
   ✅ Agora a task está REGISTRADA
   ✅ OPENAI_API_KEY está configurada
   ↓
5. Worker: execute_supply_chain_analysis(sku)
   - Cria Supply Chain Team (Agno 2.1.3)
   - Executa análise multi-agente
   - Salva resultado no banco
   ↓
6. Frontend: Polling ou WebSocket
   - Recebe resultado da análise
   - Exibe recomendação ao usuário
```

---

## 🧪 TESTE DE VALIDAÇÃO

### Comando
```bash
docker-compose exec -T api python3 -c "
from app.core.database import engine
from app.services.chat_service import get_or_create_chat_session, process_user_message
from sqlmodel import Session

message = 'Qual a demanda do produto A vantagem de ganhar sem preocupação'

with Session(engine) as session:
    chat_session = get_or_create_chat_session(session)
    response = process_user_message(session, chat_session.id, message)
    print(response.content)
"
```

### Resultado Esperado
```
✅ LLM fallback extraiu product_name: 'a vantagem de ganhar sem preocupação'
✅ LLM fallback detectou intent: 'forecast' (análise/previsão)
✅ Resolvido 'a vantagem de ganhar sem preocupação' → SKU: 84903501
🔍 DEBUG - Entities extraídas: {'sku': '84903501', 'intent': 'forecast', ...}
🔍 DEBUG - Routing: {'agent': 'supply_chain_analysis', ...}

📤 RESPOSTA:
🔍 Iniciando análise completa para 84903501...

Estou consultando:
- Previsão de demanda
- Preços de mercado
- Análise logística
- Recomendação de compra

Aguarde um momento...
```

### Logs do Worker
```
[2025-10-10 00:35:38] Task execute_agent_analysis[...] received
[2025-10-10 00:35:38] agents.task.start sku=84903501
[2025-10-10 00:35:38] agents.analysis.start sku=84903501
[2025-10-10 00:35:40] Task execute_agent_analysis[...] succeeded
```

---

## 📊 CHECKLIST

- [x] ✅ Task `agent_tasks` importada no `celery_app.py`
- [x] ✅ Worker registra a task `execute_agent_analysis`
- [x] ✅ `OPENAI_API_KEY` configurada como alias
- [x] ✅ `OPENAI_BASE_URL` apontando para OpenRouter
- [x] ✅ Teste manual validado

---

## 🎯 TIPOS DE ANÁLISE SUPORTADOS

Agora o sistema suporta análises **assíncronas** via Celery:

### 📊 Previsão de Demanda (intent: forecast)
```
"Qual a demanda do produto X?"
"Qual a média de vendas do produto X?"
"Qual o histórico do produto X?"
```

### 💰 Verificação de Preços (intent: price_check)
```
"Qual o preço do produto X?"
"Cotação do produto X?"
```

### 🛒 Decisão de Compra (intent: purchase_decision)
```
"Devo comprar o produto X?"
"Fazer pedido de X?"
```

### 🚚 Análise Logística (intent: logistics)
```
"Qual o fornecedor do produto X?"
"Prazo de entrega de X?"
```

**Todas essas perguntas agora disparam a análise completa via Celery Worker! ✅**

---

## 🔄 RESTART NECESSÁRIO

Após as correções, é necessário restart completo:

```bash
docker-compose down
docker-compose up -d
```

**Por quê?**
- Nova configuração de ambiente no `docker-compose.yml`
- Import de `agent_tasks` no `celery_app.py`
- Worker precisa recarregar as tasks

---

## 🎉 CONCLUSÃO

### Status: ✅ **SISTEMA FUNCIONAL**

**Correções Aplicadas:**
1. ✅ Task `execute_agent_analysis` registrada
2. ✅ Variáveis de ambiente configuradas
3. ✅ Worker reconhece e executa a task
4. ✅ Análises assíncronas funcionando

**Benefícios:**
- ✅ Perguntas complexas processadas em background
- ✅ API responde instantaneamente
- ✅ Worker executa análise multi-agente
- ✅ Frontend recebe resultado quando pronto

---

**Documento gerado:** 2025-10-09 21:35 BRT  
**Tipo:** Correção de Celery Task Registration  
**Status:** ✅ Aplicado e Validado
