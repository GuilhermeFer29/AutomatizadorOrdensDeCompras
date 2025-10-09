# 🏗️ Arquitetura Agno - Sistema de Automação de Ordens de Compra

## 📐 Visão Geral da Arquitetura

O sistema utiliza o framework **Agno** para orquestrar múltiplos agentes especializados que colaboram na análise e tomada de decisão sobre ordens de compra.

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND / API                              │
│                    (FastAPI Endpoints)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│               CONVERSATIONAL AGENT (NLU)                         │
│  - Extração de Entidades (Agno Agent)                           │
│  - Resolução de Contexto (RAG)                                  │
│  - Roteamento de Intents                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│               SUPPLY CHAIN TEAM (Agno Team)                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. ANALISTA DE DEMANDA                                  │  │
│  │     - Analisa estoque atual vs. mínimo                   │  │
│  │     - Avalia previsão de demanda (LightGBM)              │  │
│  │     - Decide: need_restock? (true/false)                 │  │
│  │     - Tools: lookup_product, load_demand_forecast        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. PESQUISADOR DE MERCADO                               │  │
│  │     - Scraping de preços (Mercado Livre)                 │  │
│  │     - Busca contexto web (Tavily)                        │  │
│  │     - Pesquisa enciclopédica (Wikipedia)                 │  │
│  │     - Tools: scrape_latest_price, tavily_search,         │  │
│  │              wikipedia_search                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  3. ANALISTA DE LOGÍSTICA                                │  │
│  │     - Avalia distâncias e custos de transporte           │  │
│  │     - Calcula custo total de aquisição                   │  │
│  │     - Seleciona melhor oferta                            │  │
│  │     - Tools: compute_distance                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                             ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  4. GERENTE DE COMPRAS                                   │  │
│  │     - Consolida todas as análises                        │  │
│  │     - Avalia riscos                                      │  │
│  │     - Decisão final: approve/reject/manual_review        │  │
│  │     - Gera justificativa e próximos passos               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE FORMATTER                            │
│  - Traduz resposta técnica para linguagem natural               │
│  - Formata em Markdown                                          │
│  - Adiciona emojis e estrutura                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Componentes Principais

### 1. **Conversational Agent** (`app/agents/conversational_agent.py`)

**Responsabilidade:** Orquestrador principal - interface entre usuário e sistema

**Componentes:**
- **Entity Extractor Agent (Agno):**
  - Extrai: SKU, produto, intent, quantidade
  - Usa RAG para resolver referências pronominais
  - Fallback para regex se LLM falhar

- **Session Context Manager:**
  - Mantém contexto entre mensagens
  - Armazena em banco de dados (ChatContext)

- **Intent Router:**
  - `forecast` → Supply Chain Team
  - `price_check` → Supply Chain Team
  - `stock_check` → Consulta direta ao BD
  - `purchase_decision` → Supply Chain Team
  - `logistics` → Supply Chain Team
  - `general_inquiry` → Clarificação

**Modelo:** OpenRouter (configurável via env)

---

### 2. **Supply Chain Team** (`app/agents/supply_chain_team.py`)

**Responsabilidade:** Pipeline de análise sequencial para decisão de compra

**Arquitetura Agno:**
```python
Team(
    name="SupplyChainTeam",
    agents=[
        analista_demanda,
        pesquisador_mercado,
        analista_logistica,
        gerente_compras
    ],
    mode="sequential"
)
```

**Fluxo de Dados:**
```
Input: SKU + Inquiry Reason
  ↓
Analista Demanda → { need_restock, justification, confidence_level }
  ↓
Pesquisador Mercado → { offers[], market_context }
  ↓
Analista Logística → { selected_offer, analysis_notes, alternatives[] }
  ↓
Gerente Compras → { decision, supplier, price, rationale, next_steps[], risk_assessment }
  ↓
Output: Recomendação Final
```

**Configuração do Modelo:**
- Cada agente usa `agno.models.openai.OpenAI`
- Endpoint: OpenRouter API
- Temperatura: 0.1 - 0.2 (precisão sobre criatividade)

---

### 3. **Supply Chain Toolkit** (`app/agents/tools.py`)

**Responsabilidade:** Biblioteca de ferramentas para os agentes

**Classe:** `SupplyChainToolkit(Toolkit)`

**Ferramentas:**

| Ferramenta | Função | Agente Principal |
|------------|--------|------------------|
| `lookup_product` | Consulta produto no BD | Analista Demanda |
| `load_demand_forecast` | Previsão LightGBM | Analista Demanda |
| `scrape_latest_price` | Scraping Mercado Livre | Pesquisador Mercado |
| `wikipedia_search` | Contexto enciclopédico | Pesquisador Mercado |
| `tavily_search` | Busca web atualizada | Pesquisador Mercado |
| `compute_distance` | Cálculo de distâncias | Analista Logística |

**Formato de Retorno:** JSON string (parse automático pelo Agno)

---

### 4. **RAG Service** (`app/services/rag_service.py`)

**Responsabilidade:** Retrieval-Augmented Generation para contexto semântico

**Stack Tecnológico:**
- **Vector DB:** ChromaDB (persistente)
- **Embeddings:** OpenAI `text-embedding-3-small` via OpenRouter
- **Collections:**
  - `chat_history` - Histórico de mensagens
  - `products` - Catálogo de produtos

**Fluxo RAG:**
```
User Query → Embedding (OpenRouter) → ChromaDB Query → Top-K Results → Context Injection
```

**APIs Principais:**
- `index_chat_message(message)` - Indexa mensagem
- `index_product_catalog(session)` - Indexa produtos
- `semantic_search_messages(query, session_id, k)` - Busca semântica
- `get_relevant_context(query, session)` - Contexto para NLU

---

### 5. **Agent Service** (`app/services/agent_service.py`)

**Responsabilidade:** Camada de serviço entre API e Team

**Função Principal:**
```python
execute_supply_chain_analysis(sku: str, inquiry_reason: str) -> Dict
```

**Features:**
- Logging estruturado (structlog)
- Validação de entrada
- Tratamento de exceções
- Defaults para campos obrigatórios

---

## 🔄 Fluxo de Execução Completo

### Exemplo: "Preciso comprar 50 unidades do SKU_001"

```
1. API Endpoint (/api/chat)
   ↓
2. Conversational Agent - extract_entities()
   → NLU Agent (Agno) extrai:
     {
       "sku": "SKU_001",
       "intent": "purchase_decision",
       "quantity": 50,
       "confidence": "high"
     }
   ↓
3. route_to_specialist()
   → Retorna: { "agent": "supply_chain_analysis", "async": True }
   ↓
4. execute_supply_chain_team(sku="SKU_001")
   ↓
5. Team Sequencial (Agno):
   
   a) Analista Demanda:
      - lookup_product("SKU_001") → estoque_atual=20, estoque_minimo=50
      - load_demand_forecast("SKU_001") → tendência crescente
      → need_restock=True, justification="Estoque abaixo do mínimo"
   
   b) Pesquisador Mercado:
      - scrape_latest_price("SKU_001") → R$ 150.00 (Fornecedor A)
      - tavily_search("SKU_001 preço") → contexto de mercado
      → offers=[{source: "Fornecedor A", price: 150.00, ...}]
   
   c) Analista Logística:
      - compute_distance(origem, destino) → 120 km
      - Calcula custo total → R$ 150.00 + R$ 30.00 (frete) = R$ 180.00
      → selected_offer={source: "Fornecedor A", estimated_total_cost: 180.00}
   
   d) Gerente Compras:
      - Analisa: estoque baixo + preço aceitável + logística viável
      → decision="approve", rationale="Compra recomendada...", risk_assessment="Baixo"
   ↓
6. format_agent_response()
   → Converte JSON técnico para linguagem natural com emojis
   ↓
7. Response ao usuário:
   "✅ Recomendo aprovar a compra:
    📦 Fornecedor: Fornecedor A
    💰 Preço: BRL 150.00
    📊 Quantidade: 50 unidades
    ..."
```

---

## ⚙️ Configuração OpenRouter

### Variáveis de Ambiente
```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL_NAME=mistralai/mistral-small-3.1-24b-instruct:free
```

### Como Funciona
```python
# Agno usa o cliente OpenAI internamente
OpenAI(
    model="mistralai/mistral-small-3.1-24b-instruct:free",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"  # ← Redirecionamento
)
```

OpenRouter atua como **proxy** para múltiplos provedores de LLM (Anthropic, Meta, Mistral, etc.)

---

## 🎯 Padrões de Design Utilizados

### 1. **Strategy Pattern**
Cada agente é uma estratégia especializada para uma etapa da análise.

### 2. **Chain of Responsibility**
Fluxo sequencial onde cada agente processa e enriquece o estado.

### 3. **Repository Pattern**
`SupplyChainToolkit` abstrai acesso a dados e serviços externos.

### 4. **Facade Pattern**
`agent_service.py` fornece interface simplificada para o sistema complexo.

---

## 📊 Métricas e Monitoramento

### Logs Estruturados (structlog)
```python
LOGGER.info("agents.analysis.start", sku=sku, inquiry_reason=inquiry_reason)
LOGGER.info("agents.analysis.completed", sku=sku)
LOGGER.exception("agents.analysis.error", sku=sku, error=str(exc))
```

### Métricas Importantes
- **Latência Total:** Tempo desde request até response
- **Token Usage:** Rastreado via OpenRouter dashboard
- **Cache Hit Rate:** ChromaDB (RAG)
- **Success Rate:** % de análises completas vs. erros

---

## 🔒 Segurança e Resiliência

### 1. **Validação de Entrada**
```python
if not sku.strip():
    raise ValueError("O SKU informado não pode ser vazio.")
```

### 2. **Fallbacks**
- NLU: LLM → Regex
- RAG: Embedding error → Vetor zero
- Tools: Exception → JSON com erro

### 3. **Timeouts**
Configurável no Agno via `model.timeout`

### 4. **Rate Limiting**
Gerenciado pelo OpenRouter (incluso no plano)

---

## 🚀 Performance

### Otimizações Implementadas
1. **Cache de LLM:** Cliente OpenAI reutilizado (singleton)
2. **Persistência ChromaDB:** Embeddings salvos em disco
3. **Temperature baixa:** Respostas mais determinísticas (menos tokens)
4. **Mode sequential:** Paralelização quando possível no futuro

### Benchmarks Esperados
- **Extração de Entidades:** ~2-3s
- **Team Completo:** ~15-30s (depende de scraping)
- **RAG Lookup:** ~200-500ms

---

## 🔮 Roadmap Futuro

### Melhorias Planejadas
1. **Modo Paralelo:** Agentes que não dependem entre si rodarem em paralelo
2. **Streaming:** Respostas em tempo real via Server-Sent Events
3. **Fine-tuning:** Modelo customizado para intents específicos
4. **A/B Testing:** Comparar diferentes configurações de agentes
5. **Auto-Healing:** Retry automático com fallback models

---

## 📚 Referências

- **Agno Docs:** https://docs.agno.com/
- **OpenRouter:** https://openrouter.ai/docs
- **ChromaDB:** https://docs.trychroma.com/
- **FastAPI:** https://fastapi.tiangolo.com/

---

**Última atualização:** 2025-10-09  
**Versão da Arquitetura:** 2.0 (Agno)  
**Autor:** Sistema de Automação de Ordens de Compra
