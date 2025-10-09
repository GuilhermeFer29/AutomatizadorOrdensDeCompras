# ⚡ Guia Rápido de Teste - Integração Frontend ↔ Agno

## 🎯 Objetivo
Validar que os novos agentes Agno estão funcionando corretamente com o frontend.

---

## 📋 Pré-requisitos

### 1. Instalar Dependências
```bash
# No diretório raiz do projeto
pip install agno==0.0.36 openai==1.59.5

# OU via Docker
docker-compose build --no-cache
```

### 2. Configurar Variáveis de Ambiente
Edite `.env`:
```env
OPENROUTER_API_KEY=sk-or-v1-SEU-API-KEY-AQUI
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL_NAME=mistralai/mistral-small-3.1-24b-instruct:free
```

### 3. Iniciar Serviços
```bash
# Docker (recomendado)
docker-compose up -d

# OU Local
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
celery -A app.core.celery_app worker --loglevel=info
```

---

## 🧪 Testes Rápidos

### Teste 1: Verificar Imports (30 segundos)
```bash
python3 -c "
from app.agents.supply_chain_team import create_supply_chain_team
from app.agents.conversational_agent import extract_entities

print('✅ Todos os imports funcionaram!')
print('✅ Agentes Agno carregados com sucesso!')
"
```

**Resultado esperado:**
```
✅ Todos os imports funcionaram!
✅ Agentes Agno carregados com sucesso!
```

---

### Teste 2: API de Chat (1 minuto)

#### Passo 1: Criar Sessão
```bash
curl -X POST http://localhost:8000/api/chat/sessions | jq
```

**Resultado esperado:**
```json
{
  "id": 1,
  "criado_em": "2025-10-09T19:00:00"
}
```

#### Passo 2: Enviar Mensagem Simples
```bash
curl -X POST http://localhost:8000/api/chat/sessions/1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Qual o estoque do SKU_001?"
  }' | jq
```

**Resultado esperado:**
```json
{
  "id": 2,
  "sender": "agent",
  "content": "📦 **[Nome do Produto]** (SKU: SKU_001)\n\nEstoque Atual: XX unidades\nEstoque Mínimo: XX unidades\nStatus: ✅ OK",
  "metadata": {
    "type": "stock_check",
    "sku": "SKU_001",
    "confidence": "high"
  }
}
```

---

### Teste 3: Análise Completa com Agno Team (2-3 minutos)

```bash
curl -X POST http://localhost:8000/api/chat/sessions/1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Preciso analisar a compra de 50 unidades do SKU_001"
  }' | jq
```

**Primeira Resposta (Imediata):**
```json
{
  "sender": "agent",
  "content": "🔍 Iniciando análise completa para SKU_001...\n\nEstou consultando:\n- Previsão de demanda\n- Preços de mercado\n- Análise logística\n- Recomendação de compra\n\nAguarde um momento...",
  "metadata": {
    "type": "analysis_started",
    "sku": "SKU_001",
    "task_id": "abc-123",
    "async": true
  }
}
```

**Aguarde ~30-60 segundos e consulte novamente:**
```bash
curl http://localhost:8000/api/chat/sessions/1/messages | jq
```

**Resposta Final (do Team Agno):**
```json
{
  "sender": "agent",
  "content": "✅ Análise completa finalizada!\n\n📊 **Recomendação:** Aprovar compra\n📦 **Fornecedor:** Fornecedor A\n💰 **Preço:** BRL 150.00\n📈 **Quantidade sugerida:** 50 unidades\n\n**Justificativa:**\nEstoque atual (20 unidades) está abaixo do mínimo (50 unidades)...",
  "metadata": {
    "type": "analysis_completed",
    "decision": "approve",
    "sku": "SKU_001"
  }
}
```

---

### Teste 4: Verificar Logs do Agno Team (Opcional)

```bash
# Docker
docker-compose logs -f celery-worker | grep "agents.analysis"

# Local
tail -f celery.log | grep "agents.analysis"
```

**Logs esperados:**
```
agents.analysis.start sku=SKU_001
agents.tool.lookup_product sku=SKU_001
agents.tool.load_demand_forecast sku=SKU_001
agents.team.agent_completed agent=AnalistaDemanda
agents.tool.scrape_latest_price sku=SKU_001
agents.team.agent_completed agent=PesquisadorMercado
agents.team.agent_completed agent=AnalistaLogistica
agents.team.agent_completed agent=GerenteCompras
agents.analysis.completed sku=SKU_001 decision=approve
```

---

## 🔍 Validação Detalhada

### Checklist de Funcionalidade

- [ ] **API responde** no endpoint `/api/chat/sessions/{id}/messages`
- [ ] **NLU Agno** extrai SKU corretamente da mensagem
- [ ] **Roteamento** identifica o intent correto (purchase_decision)
- [ ] **Celery Task** é disparada em segundo plano
- [ ] **Supply Chain Team** é criado com 4 agentes Agno
- [ ] **Agentes executam** em modo "coordinate"
- [ ] **Ferramentas** são chamadas (lookup_product, scrape_latest_price, etc)
- [ ] **Resposta final** é formatada e retornada ao frontend
- [ ] **Metadata** contém informações estruturadas (decision, sku, etc)

---

## 🐛 Troubleshooting Rápido

### Erro: "No module named 'agno'"
```bash
# Solução
pip install agno==0.0.36
# ou
docker-compose build --no-cache
docker-compose up -d
```

### Erro: "OPENROUTER_API_KEY not found"
```bash
# Solução
echo "OPENROUTER_API_KEY=sk-or-v1-..." >> .env
docker-compose restart api
```

### Erro: Task Celery não executa
```bash
# Verificar se worker está rodando
docker-compose ps | grep celery

# Reiniciar worker
docker-compose restart celery-worker

# Ver logs
docker-compose logs -f celery-worker
```

### Resposta vazia ou erro 500
```bash
# Ver logs da API
docker-compose logs -f api

# Verificar banco de dados
docker-compose exec db mysql -u root -p
mysql> USE seu_database;
mysql> SELECT * FROM produto LIMIT 5;
```

---

## 📊 Fluxo Resumido para Frontend Developer

```
1. Usuario digita no chat
   ↓
2. Frontend POST /api/chat/sessions/{id}/messages
   ↓
3. Backend processa com Agent Agno (NLU)
   ↓
4. Se for análise complexa → Dispara Celery Task
   ↓
5. Team Agno (4 agentes) executa análise
   ↓
6. Resposta formatada volta para frontend
   ↓
7. Frontend mostra resposta ao usuário
```

---

## 🎯 Endpoints Importantes para Frontend

### Chat
```
POST   /api/chat/sessions                    # Criar sessão
GET    /api/chat/sessions/{id}/messages      # Histórico
POST   /api/chat/sessions/{id}/messages      # Enviar mensagem ⭐
WS     /api/chat/ws/{id}                     # WebSocket tempo real
POST   /api/chat/sessions/{id}/actions       # Executar ação (aprovar compra)
```

### Agentes (Dashboard)
```
GET    /api/agents/                          # Listar agentes
POST   /api/agents/{id}/run                  # Executar agente ⭐
POST   /api/agents/{id}/pause                # Pausar agente
POST   /api/agents/{id}/activate             # Ativar agente
```

---

## ✅ Validação Final

Execute todos os testes acima. Se tudo passar:

✅ **Integração 100% funcional!**
- Agentes Agno refatorados
- API moderna implementada
- Frontend conectado corretamente
- Sistema pronto para uso

---

**Tempo estimado de teste completo:** 5-10 minutos  
**Documento criado:** 2025-10-09  
**Status:** Pronto para validação
