# ✅ Checklist de Validação da Migração - LangChain → Agno

## 📋 Pré-requisitos

- [ ] Variáveis de ambiente configuradas no `.env`:
  ```bash
  OPENROUTER_API_KEY=sk-or-...
  OPENROUTER_API_BASE=https://openrouter.ai/api/v1
  OPENROUTER_MODEL_NAME=mistralai/mistral-small-3.1-24b-instruct:free
  ```

- [ ] Dependências instaladas:
  ```bash
  pip install -r requirements.txt
  # ou
  docker-compose build
  ```

---

## 🔍 Testes de Componentes Individuais

### 1. Tools (Ferramentas)
```python
from app.agents.tools import SupplyChainToolkit

toolkit = SupplyChainToolkit()

# Teste 1: Lookup produto
result = toolkit.lookup_product("SKU_001")
print("✅ Lookup produto:", result)

# Teste 2: Forecast
result = toolkit.load_demand_forecast("SKU_001", horizon_days=7)
print("✅ Forecast:", result)

# Teste 3: Wikipedia
result = toolkit.wikipedia_search("supply chain management")
print("✅ Wikipedia:", result[:100])
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

### 2. Conversational Agent (NLU)
```python
from app.agents.conversational_agent import extract_entities
from app.core.database import engine
from sqlmodel import Session

with Session(engine) as session:
    # Teste 1: Extração de SKU
    result = extract_entities("Analisar o SKU_001", session, session_id=1)
    assert result.get("sku") == "SKU_001"
    print("✅ Extração de SKU")
    
    # Teste 2: Extração de intent
    result = extract_entities("Qual o preço do SKU_002?", session, session_id=1)
    assert result.get("intent") == "price_check"
    print("✅ Detecção de intent")
    
    # Teste 3: Extração de quantidade
    result = extract_entities("Preciso comprar 50 unidades do SKU_003", session, session_id=1)
    assert result.get("quantity") == 50
    print("✅ Extração de quantidade")
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

### 3. RAG Service
```python
from app.services.rag_service import (
    index_product_catalog,
    semantic_search_messages,
    get_relevant_context
)
from app.core.database import engine
from sqlmodel import Session

with Session(engine) as session:
    # Teste 1: Indexar catálogo
    index_product_catalog(session)
    print("✅ Catálogo indexado")
    
    # Teste 2: Busca semântica
    results = semantic_search_messages("estoque baixo", k=3)
    print(f"✅ Encontrados {len(results)} resultados")
    
    # Teste 3: Contexto RAG
    context = get_relevant_context("SKU_001", session)
    print("✅ Contexto RAG obtido")
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

### 4. Supply Chain Team (Agentes)
```python
from app.agents.supply_chain_team import execute_supply_chain_team

# Teste completo do fluxo de agentes
try:
    result = execute_supply_chain_team(sku="SKU_001", inquiry_reason="Teste de validação")
    
    # Verificações
    assert "recommendation" in result
    assert "product_sku" in result
    assert result["product_sku"] == "SKU_001"
    
    recommendation = result["recommendation"]
    assert "decision" in recommendation
    assert recommendation["decision"] in ["approve", "reject", "manual_review"]
    
    print("✅ Team executado com sucesso!")
    print(f"   Decisão: {recommendation['decision']}")
    print(f"   Justificativa: {recommendation.get('rationale', 'N/A')[:100]}")
    
except Exception as e:
    print(f"❌ Erro: {e}")
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

### 5. Agent Service
```python
from app.services.agent_service import execute_supply_chain_analysis

# Teste do serviço completo
try:
    result = execute_supply_chain_analysis(sku="SKU_001", inquiry_reason="Validação pós-migração")
    
    # Verificações
    assert result is not None
    assert "recommendation" in result
    
    print("✅ Agent Service funcionando!")
    print(f"   SKU: {result.get('product_sku')}")
    print(f"   Decisão: {result.get('recommendation', {}).get('decision')}")
    
except Exception as e:
    print(f"❌ Erro: {e}")
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

## 🌐 Testes de API

### 1. Endpoint de Chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analisar compra do SKU_001",
    "session_id": 1
  }' | jq .
```

**Resposta esperada:** JSON com análise completa e recomendação

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

### 2. Endpoint de Agentes
```bash
# Listar agentes
curl http://localhost:8000/api/agents | jq .

# Executar análise via agente
curl -X POST http://localhost:8000/api/agents/1/run | jq .
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

## 🔄 Testes de Integração

### Fluxo Completo: Chat → NLU → Team → Resposta
```python
from app.agents.conversational_agent import (
    extract_entities,
    route_to_specialist,
    format_agent_response
)
from app.services.agent_service import execute_supply_chain_analysis
from app.core.database import engine
from sqlmodel import Session

with Session(engine) as session:
    # 1. Mensagem do usuário
    user_message = "Preciso comprar 100 unidades do SKU_001"
    
    # 2. Extração de entidades (NLU)
    entities = extract_entities(user_message, session, session_id=1)
    print(f"✅ Entidades: {entities}")
    
    # 3. Roteamento
    routing = route_to_specialist(entities["intent"], entities)
    print(f"✅ Roteamento: {routing}")
    
    # 4. Execução do team (se necessário)
    if routing["agent"] == "supply_chain_analysis":
        analysis = execute_supply_chain_analysis(
            sku=entities["sku"],
            inquiry_reason=user_message
        )
        print(f"✅ Análise completa")
        
        # 5. Formatação da resposta
        response = format_agent_response(analysis, entities["intent"])
        print(f"✅ Resposta formatada:\n{response}")
```

**Status:** [ ] Passou | [ ] Falhou | [ ] Não testado

---

## 🧹 Limpeza (Opcional)

Após validar que tudo funciona:

- [ ] Remover arquivo antigo:
  ```bash
  rm app/agents/supply_chain_graph.py
  ```

- [ ] Remover dependências antigas do sistema (se instaladas globalmente):
  ```bash
  pip uninstall langchain langgraph langchain-community langchain-openai langchain-experimental langchain-chroma -y
  ```

- [ ] Limpar cache do Python:
  ```bash
  find . -type d -name "__pycache__" -exec rm -r {} +
  find . -type f -name "*.pyc" -delete
  ```

---

## 📊 Métricas de Performance (Opcional)

Compare a performance antes e depois:

```python
import time
from app.services.agent_service import execute_supply_chain_analysis

# Teste de performance
start = time.time()
result = execute_supply_chain_analysis(sku="SKU_001")
elapsed = time.time() - start

print(f"⏱️  Tempo de execução: {elapsed:.2f}s")
print(f"📊 Tokens usados: Verificar logs do OpenRouter")
```

**Tempo médio esperado:** 10-30s (dependendo do modelo e latência da rede)

---

## ✅ Checklist Final

- [ ] Todos os testes de componentes passaram
- [ ] Todos os testes de API passaram
- [ ] Teste de integração completo passou
- [ ] Performance está aceitável
- [ ] Logs não mostram erros relacionados ao LangChain
- [ ] Arquivo `supply_chain_graph.py` removido (opcional)
- [ ] Documentação atualizada
- [ ] Time notificado sobre a migração

---

## 🐛 Troubleshooting

### Erro: "No module named 'langchain'"
- **Causa:** Cache do Python ainda referencia imports antigos
- **Solução:** 
  ```bash
  find . -type d -name "__pycache__" -exec rm -r {} +
  docker-compose restart  # se usando Docker
  ```

### Erro: "OpenRouter API key not found"
- **Causa:** Variáveis de ambiente não configuradas
- **Solução:** Verificar `.env` e reiniciar containers

### Erro: "Agent response is not valid JSON"
- **Causa:** Modelo retornando markdown ao invés de JSON puro
- **Solução:** O código já trata isso, mas se persistir, ajuste temperatura para 0.1

### Erro: "ChromaDB collection not found"
- **Causa:** Collections não foram criadas
- **Solução:** Executar `index_product_catalog()` novamente

---

## 📞 Contatos

- **Documentação Agno:** https://docs.agno.com/
- **Issues do Projeto:** [Link do repositório]
- **Responsável pela Migração:** [Seu nome]

---

**Última atualização:** 2025-10-09  
**Versão do documento:** 1.0
