# 📚 DOCUMENTAÇÃO TÉCNICA END-TO-END

## Sistema de Automação Inteligente de Ordens de Compra para PMI

**Versão:** 1.2.0 | **Data:** 14/01/2026 | **Status:** ✅ Produção

---

# 📋 ÍNDICE COMPLETO

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Arquitetura Técnica](#2-arquitetura-técnica)
3. [Modelos de Dados (12 Entidades)](#3-modelos-de-dados)
4. [Sistema Multi-Agente](#4-sistema-multi-agente)
5. [Ferramentas dos Agentes (Tools)](#5-ferramentas-dos-agentes)
6. [Serviços de Backend (17 Services)](#6-serviços-de-backend)
7. [API REST Completa (50+ Endpoints)](#7-api-rest-completa)
8. [Machine Learning](#8-machine-learning)
9. [RAG - Retrieval Augmented Generation](#9-rag)
10. [Sistema de Tarefas Assíncronas](#10-tarefas-assíncronas)
11. [Frontend React](#11-frontend)
12. [Infraestrutura Docker](#12-infraestrutura-docker)
13. [Fluxos End-to-End](#13-fluxos-end-to-end)
14. [Configurações e Variáveis](#14-configurações)
15. [Guia de Troubleshooting](#15-troubleshooting)

---

# 1. VISÃO GERAL DO SISTEMA

## 1.1 Objetivo

Sistema de IA desenvolvido para **automatizar decisões de compra** em pequenas e médias indústrias (PMI), utilizando:

- **Agentes de IA colaborativos** (Multi-Agent System)
- **Machine Learning** para previsão de demanda e preços
- **RAG** (Retrieval-Augmented Generation) para conhecimento de produtos
- **Chat inteligente** com linguagem natural

## 1.2 Capacidades

| Capacidade | Descrição | Tecnologia |
|------------|-----------|------------|
| 🤖 Chat IA | Conversa natural sobre produtos e compras | Agno + Gemini 2.5 |
| 📊 Previsão ML | Demanda e preços futuros | StatsForecast + LightGBM |
| 🔍 Busca Semântica | Encontrar produtos por descrição | ChromaDB + Embeddings |
| 📋 Ordens Automáticas | Criação e aprovação de compras | Workflow multi-etapas |
| 📈 Dashboard | KPIs, alertas e métricas | React + Recharts |
| 📝 Auditoria | Log de todas as decisões IA | Trilha completa |

---

# 2. ARQUITETURA TÉCNICA

## 2.1 Diagrama de Alto Nível

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Vite)                              │
│                    TypeScript + TailwindCSS + shadcn/ui                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Dashboard  │  Chat IA  │  Catálogo  │  Ordens  │  Fornecedores │  Auditoria│
└─────────────────────────────────────────────────────────────────────────────┘
                              ↓ HTTP REST / WebSocket
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ROUTERS (16)     │  SERVICES (17)    │  AGENTS (5)      │  ML (4)          │
│  ├ api_chat       │  ├ chat_service   │  ├ conversational│  ├ prediction    │
│  ├ api_product    │  ├ rag_service    │  ├ supply_team   │  ├ training      │
│  ├ api_order      │  ├ ml_service     │  ├ tools.py      │  └ model_manager │
│  ├ ml_router      │  ├ dashboard      │  └ llm_config    │                  │
│  └ ...            │  └ ...            │                  │                  │
└─────────────────────────────────────────────────────────────────────────────┘
        ↓                      ↓                      ↓
┌──────────────┐    ┌──────────────────┐    ┌───────────────────────┐
│   MySQL 8.0  │    │    ChromaDB      │    │        Redis          │
│ 12 Tabelas   │    │  Vector Store    │    │   Broker + Pub/Sub    │
└──────────────┘    └──────────────────┘    └───────────────────────┘
                                                       ↓
                    ┌──────────────────────────────────────────────┐
                    │              CELERY WORKERS                   │
                    │   Tasks: ML Training, Agent Analysis          │
                    └──────────────────────────────────────────────┘
```

## 2.2 Stack Tecnológico Detalhado

### Backend

| Componente | Tecnologia | Versão | Função |
|------------|------------|--------|--------|
| Framework Web | FastAPI | 0.100+ | API REST assíncrona |
| ORM | SQLModel | 0.0.14+ | Mapeamento objeto-relacional |
| Validação | Pydantic | 2.0+ | Schemas e validação |
| Task Queue | Celery | 5.3+ | Processamento assíncrono |
| Broker | Redis | 7+ | Mensageria e cache |
| Banco | MySQL | 8.0 | Persistência principal |
| Logging | structlog | - | Logs estruturados |

### IA/ML

| Componente | Tecnologia | Função |
|------------|------------|--------|
| Framework Agentes | Agno | Orquestração multi-agente |
| LLM Principal | Gemini 2.5 Flash | Reasoning e geração |
| Embeddings | text-embedding-004 | Vetorização semântica |
| Vector Store | ChromaDB | Armazenamento vetorial |
| RAG | LangChain | Pipeline de retrieval |
| Time Series | StatsForecast | Previsão de demanda |
| Previsão Preço | LightGBM | Gradient boosting |
| Timezone | pytz | America/Sao_Paulo |

### Frontend

| Componente | Tecnologia | Versão |
|------------|------------|--------|
| Framework | React | 18+ |
| Build | Vite | 5+ |
| Linguagem | TypeScript | 5+ |
| Estilização | TailwindCSS | 3+ |
| Componentes | shadcn/ui | - |
| Gráficos | Recharts | - |
| HTTP | Axios | - |
| Estado | Context API | - |

---

# 3. MODELOS DE DADOS

## 3.1 Diagrama ER

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│  Produto    │───1:N─│  VendasHistoricas│       │ Fornecedor  │
│  (produtos) │       │                  │       │(fornecedores)│
├─────────────┤       ├──────────────────┤       ├─────────────┤
│ id          │       │ id               │       │ id          │
│ nome        │       │ produto_id (FK)  │       │ nome        │
│ sku (UK)    │       │ data_venda       │       │ cep         │
│ categoria   │       │ quantidade       │       │ confiabilidade│
│ estoque_atual│      │ receita          │       │ prazo_entrega│
│ estoque_minimo│     └──────────────────┘       └─────────────┘
└─────────────┘              │                          │
      │                      │                          │
      │1:N                   │                          │1:N
      ↓                      │                          ↓
┌──────────────────┐         │              ┌───────────────────┐
│ PrecosHistoricos │         │              │   OfertaProduto   │
├──────────────────┤         │              ├───────────────────┤
│ id               │         │              │ id                │
│ produto_id (FK)  │         │              │ produto_id (FK)   │
│ fornecedor       │         │              │ fornecedor_id (FK)│
│ preco            │         │              │ preco_ofertado    │
│ coletado_em      │         │              │ estoque_disponivel│
└──────────────────┘         │              │ validade_oferta   │
      │                      │              └───────────────────┘
      │1:N                   │
      ↓                      │
┌──────────────────┐         │
│  ModeloPredicao  │         │
├──────────────────┤         │
│ id               │         │
│ produto_id (FK)  │←────────┘
│ modelo_tipo      │
│ metricas (JSON)  │
│ treinado_em      │
└──────────────────┘
```

## 3.2 Entidades Detalhadas

### Produto (`produtos`)

```python
class Produto(SQLModel, table=True):
    __tablename__ = "produtos"
    
    id: Optional[int]           # PK auto-incremento
    nome: str                   # Nome do produto
    sku: str                    # SKU único (ex: "MEC-001")
    categoria: Optional[str]    # Categoria (ex: "Ferramentas")
    estoque_atual: int          # Quantidade em estoque (≥0)
    estoque_minimo: int         # Ponto de reposição (≥0)
    criado_em: datetime         # Data de criação (UTC)
    atualizado_em: datetime     # Última atualização (UTC)
    
    # Relacionamentos
    vendas: List[VendasHistoricas]
    precos: List[PrecosHistoricos]
    modelos_predicao: List[ModeloPredicao]
```

**Campos de negócio:**
- `estoque_atual >= estoque_minimo` → Status "OK"
- `estoque_atual < estoque_minimo` → Status "ALERTA" (precisa repor)

### VendasHistoricas (`vendas_historicas`)

```python
class VendasHistoricas(SQLModel, table=True):
    id: Optional[int]
    produto_id: int             # FK para produtos
    data_venda: datetime        # Data da venda
    quantidade: int             # Unidades vendidas (≥0)
    receita: Decimal            # Valor total (≥0.00)
    criado_em: datetime
```

**Uso:** Base para cálculo de demanda média e previsões ML.

### PrecosHistoricos (`precos_historicos`)

```python
class PrecosHistoricos(SQLModel, table=True):
    id: Optional[int]
    produto_id: int             # FK para produtos
    fornecedor: Optional[str]   # Nome do fornecedor
    preco: Decimal              # Preço coletado
    moeda: str                  # ISO (padrão: "BRL")
    coletado_em: datetime       # Data da coleta
    is_synthetic: bool          # Se foi gerado por ML
```

### Fornecedor (`fornecedores`)

```python
class Fornecedor(SQLModel, table=True):
    id: Optional[int]
    nome: str                   # Nome da empresa
    cep: Optional[str]          # CEP para cálculo logístico
    latitude: Optional[float]   # Coordenadas
    longitude: Optional[float]
    confiabilidade: float       # Score 0.0 a 1.0
    prazo_entrega_dias: int     # Dias para entrega (1-60)
```

### OfertaProduto (`ofertas_produtos`)

```python
class OfertaProduto(SQLModel, table=True):
    id: Optional[int]
    produto_id: int             # FK para produtos
    fornecedor_id: int          # FK para fornecedores
    preco_ofertado: Decimal     # Preço unitário
    estoque_disponivel: int     # Qtd disponível no fornecedor
    validade_oferta: datetime   # Expiração da oferta
```

### OrdemDeCompra (`ordens_de_compra`)

```python
class OrdemDeCompra(SQLModel, table=True):
    id: Optional[int]
    produto_id: int             # FK para produtos
    fornecedor_id: int          # FK para fornecedores
    quantidade: int             # Quantidade a comprar
    valor: Decimal              # Valor total
    status: str                 # pending|approved|cancelled|rejected
    origem: str                 # "Automática" ou "Manual"
    autoridade_nivel: int       # 1=Operacional, 2=Gerencial, 3=Diretoria
    aprovado_por: Optional[str] # Nome do aprovador
    data_criacao: datetime
    data_aprovacao: datetime
    justificativa: str          # Razão da decisão
```

### User (`users`)

```python
class User(SQLModel, table=True):
    id: Optional[int]
    email: str                  # Email único (login)
    hashed_password: str        # Senha hasheada (bcrypt)
    is_active: bool             # Conta ativa
    full_name: Optional[str]    # Nome completo
```

### ModeloPredicao (`modelos_predicao`)

```python
class ModeloPredicao(SQLModel, table=True):
    id: Optional[int]
    produto_id: int             # FK para produtos
    modelo_tipo: str            # "LightGBM", "AutoARIMA", etc
    versao: str                 # Versão do modelo
    caminho_modelo: str         # Path do arquivo .pkl
    metricas: Dict              # JSON com MAPE, RMSE, etc
    treinado_em: datetime
```

### ModeloGlobal (`modelos_globais`)

```python
class ModeloGlobal(SQLModel, table=True):
    id: Optional[int]
    modelo_tipo: str            # Tipo do modelo agregado
    versao: str
    holdout_dias: int           # Dias reservados para validação
    caminho_modelo: str
    caminho_relatorio: str      # Path do relatório HTML
    metricas: Dict
    treinado_em: datetime
```

### Agente (`agentes`)

```python
class Agente(SQLModel, table=True):
    id: Optional[int]
    nome: str                   # Nome único (ex: "SupplyChainTeam")
    descricao: str              # O que faz
    status: str                 # active|inactive
    ultima_execucao: datetime   # Última vez que rodou
```

### AuditoriaDecisao (`auditoria_decisoes`)

```python
class AuditoriaDecisao(SQLModel, table=True):
    id: Optional[int]
    agente_nome: str            # Qual agente tomou a decisão
    sku: str                    # Produto analisado
    acao: str                   # approve|reject|recommend
    decisao: str                # JSON com detalhes
    raciocinio: str             # Explicação completa
    contexto: str               # JSON com dados usados
    usuario_id: str             # Quem solicitou
    data_decisao: datetime
    ip_origem: str
```

### Chat (3 tabelas)

```python
# ChatSession - Uma conversa
class ChatSession(SQLModel, table=True):
    id: Optional[int]
    criado_em: datetime

# ChatMessage - Mensagens da conversa
class ChatMessage(SQLModel, table=True):
    id: Optional[int]
    session_id: int             # FK para chat_sessions
    sender: str                 # 'human' | 'agent' | 'system'
    content: str                # TEXT (respostas longas)
    metadata_json: str          # JSON com dados extras
    criado_em: datetime

# ChatContext - Estado da conversa
class ChatContext(SQLModel, table=True):
    id: Optional[int]
    session_id: int             # FK para chat_sessions
    key: str                    # Ex: 'current_sku'
    value: str                  # Valor serializado
    atualizado_em: datetime
```

---

# 4. SISTEMA MULTI-AGENTE

## 4.1 Arquitetura Agno

O sistema utiliza o framework **Agno** para orquestrar múltiplos agentes de IA:

```
┌─────────────────────────────────────────────────────────────┐
│                    AGNO FRAMEWORK                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐     ┌───────────────────────────────┐  │
│  │  Conversational │     │      Supply Chain Team        │  │
│  │     Agent       │────▶│  ┌─────────────────────────┐  │  │
│  │                 │     │  │   AnalistaDemanda       │  │  │
│  │  - RAG Search   │     │  │   (Previsão demanda)    │  │  │
│  │  - Intent Det.  │     │  ├─────────────────────────┤  │  │
│  │  - Tool Calling │     │  │   ComparadorFornecedor  │  │  │
│  └─────────────────┘     │  │   (Preços e ofertas)    │  │  │
│                          │  ├─────────────────────────┤  │  │
│                          │  │   AnalistaLogistico     │  │  │
│                          │  │   (Custos e prazos)     │  │  │
│                          │  ├─────────────────────────┤  │  │
│                          │  │   DecisionMaker         │  │  │
│                          │  │   (Decisão final)       │  │  │
│                          │  └─────────────────────────┘  │  │
│                          └───────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 4.2 Agente Conversacional

**Arquivo:** `app/agents/conversational_agent.py`

**Função:** Interface de chat inteligente com capacidade de:
- Responder perguntas sobre produtos (via RAG)
- Delegar análises complexas ao SupplyChainTeam
- Manter contexto da conversa (memória SQLite)

**Funções principais:**

| Função | Descrição |
|--------|-----------|
| `get_conversational_agent(session_id)` | Cria instância do agente |
| `extract_entities(message)` | Extrai SKU e intenção da mensagem |
| `save_session_context(session, key, value)` | Salva contexto |
| `format_agent_response(result)` | Formata resultado para Markdown |

**Configuração do Agente:**

```python
agent = Agent(
    name="PurchaseAssistant",
    model=get_llm_model(),           # Gemini 2.5 Flash
    instructions=instructions,        # Prompt sistema
    knowledge=load_knowledge_base(),  # RAG ChromaDB
    search_knowledge=True,            # Busca automática
    tools=[                           # 7 ferramentas disponíveis
        get_product_info,
        search_market_price,
        get_forecast_tool,
        get_price_forecast_for_sku,
        find_supplier_offers_for_sku,
        run_full_purchase_analysis,
        create_purchase_order_tool
    ],
    db=SqliteDb(db_file="data/agent_memory.db"),
    markdown=True,
)
```

## 4.3 Supply Chain Team

**Arquivo:** `app/agents/supply_chain_team.py`

**Função:** Equipe de 4 agentes especializados que colaboram para tomar decisões de compra.

### Agentes do Time

| Agente | Papel | Output |
|--------|-------|--------|
| **AnalistaDemanda** | Analisa previsão de demanda | JSON com need_restock, justification |
| **ComparadorFornecedor** | Compara ofertas de fornecedores | JSON com ofertas e melhor opção |
| **AnalistaLogistico** | Avalia custos logísticos | JSON com custos, prazos |
| **DecisionMaker** | Decisão final integrada | JSON com decisão (approve/reject) |

### Fluxo de Colaboração

```
┌─────────────────────┐
│   Inquiry Input     │  "Preciso comprar 50 unidades do MEC-001"
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  AnalistaDemanda    │  Analisa se precisa repor estoque
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ ComparadorFornecedor│  Busca melhores ofertas
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  AnalistaLogistico  │  Calcula custos totais
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│    DecisionMaker    │  Toma decisão final
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│    JSON Output      │  { "decision": "approve", "quantity": 50, ... }
└─────────────────────┘
```

### Funções principais

| Função | Descrição |
|--------|-----------|
| `create_supply_chain_team()` | Cria o Team Agno |
| `run_supply_chain_analysis(inquiry, max_retries)` | Executa análise completa |
| `execute_supply_chain_team(sku, reason)` | Wrapper de compatibilidade |
| `parse_team_json(output_text)` | Extrai JSON da resposta |
| `is_output_rate_limited(output)` | Detecta erro 429 |

---

# 5. FERRAMENTAS DOS AGENTES

## 5.1 Lista Completa de Tools

**Arquivo:** `app/agents/tools.py`

| Tool | Assinatura | Descrição |
|------|------------|-----------|
| `get_product_info` | `(product_sku: str) -> str` | Busca info do produto no BD |
| `search_market_price` | `(product_sku: str) -> str` | Scraping de preço externo |
| `get_forecast_tool` | `(product_sku: str) -> str` | Previsão de demanda |
| `get_price_forecast_for_sku` | `(sku: str, days_ahead: int) -> str` | Previsão de preço ML |
| `find_supplier_offers_for_sku` | `(sku: str) -> str` | Ofertas de fornecedores |
| `run_full_purchase_analysis` | `(sku: str, reason: str) -> str` | Análise completa |
| `create_purchase_order_tool` | `(sku, qty, price, supplier) -> str` | Cria ordem de compra |

## 5.2 Detalhamento das Tools

### get_product_info

```python
def get_product_info(product_sku: str) -> str:
    """
    Busca informações detalhadas de um produto no banco de dados.
    
    Returns: JSON com:
    - sku, nome, categoria
    - estoque_atual, estoque_minimo
    - preco_atual (último preço)
    - status_reposicao ("OK" ou "ALERTA")
    """
```

**Exemplo de retorno:**
```json
{
  "sku": "MEC-001",
  "nome": "Rolamento 6205-2RS",
  "estoque_atual": 45,
  "estoque_minimo": 20,
  "categoria": "Mecânica",
  "preco_atual": 23.50,
  "status_reposicao": "OK"
}
```

### get_forecast_tool

```python
def get_forecast_tool(product_sku: str) -> str:
    """
    Obtém previsão de demanda futura.
    
    Usa timezone: America/Sao_Paulo (UTC-3)
    
    Returns: JSON com:
    - sku
    - forecast: [{"date": "2026-01-15", "demand": 110}, ...]
    - average_demand
    - generated_at
    """
```

### find_supplier_offers_for_sku

```python
def find_supplier_offers_for_sku(sku: str) -> str:
    """
    Busca ofertas de fornecedores cadastradas.
    
    Returns: JSON com:
    - ofertas: lista de {fornecedor, preco, prazo, confiabilidade}
    - melhor_oferta: a mais vantajosa
    - total_ofertas: quantidade
    """
```

### create_purchase_order_tool

```python
def create_purchase_order_tool(
    sku: str,
    quantity: int,
    price_per_unit: float,
    supplier: str = "Agente de IA"
) -> str:
    """
    Cria uma ordem de compra no sistema.
    
    Returns: JSON com:
    - success: true/false
    - order_id: ID da ordem criada
    - message: detalhes
    """
```

---

# 6. SERVIÇOS DE BACKEND

## 6.1 Lista de Services (17)

| Serviço | Arquivo | Função |
|---------|---------|--------|
| chat_service | chat_service.py | Processamento de mensagens |
| rag_service | rag_service.py | RAG com LangChain |
| rag_sync_service | rag_sync_service.py | Sincronização produtos→ChromaDB |
| ml_service | ml_service.py | Previsões ML |
| dashboard_service | dashboard_service.py | KPIs e alertas |
| agent_service | agent_service.py | Execução de agentes |
| order_service | order_service.py | CRUD de ordens |
| product_service | product_service.py | CRUD de produtos |
| scraping_service | scraping_service.py | Busca preços externos |
| chroma_client | chroma_client.py | Singleton ChromaDB |
| hybrid_query_service | hybrid_query_service.py | Query híbrida SQL+RAG |
| redis_events | redis_events.py | Pub/Sub Redis |
| websocket_manager | websocket_manager.py | Conexões WebSocket |
| sales_ingestion_service | sales_ingestion_service.py | Ingestão de vendas |
| sql_query_tool | sql_query_tool.py | NL→SQL |
| task_service | task_service.py | Status de tasks Celery |

## 6.2 Serviços Principais

### chat_service.py

**Funções:**

| Função | Descrição |
|--------|-----------|
| `get_or_create_chat_session(session, session_id)` | Obtém ou cria sessão |
| `get_chat_history(session, session_id)` | Retorna histórico |
| `add_chat_message(session, sender, content, metadata)` | Adiciona mensagem |
| `process_user_message(session, session_id, message)` | **Principal:** processa msg |
| `handle_natural_conversation(session, question, entities)` | Conversa via Agno |
| `handle_supply_chain_analysis(session, entities)` | Dispara análise async |

**Fluxo de process_user_message:**

```
1. Salva mensagem do usuário
2. Extrai entidades (SKU, intent)
3. Salva SKU no contexto
4. DECISÃO:
   - intent in [analise_compra, forecast, logistics] + sku? 
     → handle_supply_chain_analysis (async)
   - Senão → handle_natural_conversation (RAG)
5. Salva resposta do agente
6. Retorna resposta
```

### rag_service.py

**Funções:**

| Função | Descrição |
|--------|-----------|
| `get_vector_store()` | Retorna ChromaDB LangChain |
| `index_product_catalog(db_session)` | Indexa todos produtos |
| `create_rag_chain()` | Cria chain RAG completa |
| `query_product_catalog_with_google_rag(query, k)` | Busca semântica |

**Pipeline RAG:**

```
Query → Embeddings → ChromaDB → Top-K Docs → Prompt → Gemini → Resposta
```

### dashboard_service.py

**Funções:**

| Função | Retorno |
|--------|---------|
| `get_dashboard_kpis(session)` | economy, automatedOrders, stockLevel, modelAccuracy |
| `get_dashboard_alerts(session)` | Lista de alertas (error, warning, success) |
| `get_dashboard_summary(session)` | KPIs + Alertas combinados |

**Cálculo de KPIs:**

| KPI | Fórmula |
|-----|---------|
| economy | Σ(preço_médio - melhor_oferta) × quantidade_comprada |
| automatedOrders | COUNT ordens WHERE origem='Automática' AND status='approved' |
| stockLevel | Crítico (<10%), Atenção (<30%), Saudável (≥30%) |
| modelAccuracy | 100 - AVG(MAPE) dos modelos treinados |

---

# 7. API REST COMPLETA

## 7.1 Visão Geral

| Prefixo | Módulo | Endpoints |
|---------|--------|-----------|
| `/api/chat` | api_chat_router | 7 |
| `/api/products` | api_product_router | 8 |
| `/api/orders` | api_order_router | 5 |
| `/api/suppliers` | api_supplier_router | 8 |
| `/api/audit` | api_audit_router | 3 |
| `/api/agents` | api_agent_router | 3 |
| `/api/rag` | rag_router | 3 |
| `/api/dashboard` | api_dashboard_router | 2 |
| `/ml` | ml_router | 9 |
| `/auth` | auth_router | 3 |
| **Total** | | **~50** |

## 7.2 Endpoints Detalhados

### Chat (`/api/chat`)

```http
GET  /sessions              # Lista sessões (limit=20)
POST /sessions              # Cria nova sessão
DELETE /sessions/{id}       # Deleta sessão e mensagens
GET  /sessions/{id}/messages # Histórico da sessão
POST /sessions/{id}/messages # Envia mensagem (processa com IA)
POST /sessions/{id}/actions  # Executa ação de botão
WS   /ws/{session_id}        # WebSocket real-time
```

### Produtos (`/api/products`)

```http
GET    /                    # Lista produtos (search, category)
GET    /{id}                # Detalhes do produto
GET    /{sku}/price-history # Histórico de preços (limit=30)
POST   /                    # Criar produto
PUT    /{id}                # Atualizar produto
DELETE /{id}                # Deletar produto
POST   /{id}/ingest-price   # Ingere preço manualmente
GET    /categories          # Lista categorias únicas
```

### Ordens (`/api/orders`)

```http
GET  /                      # Lista ordens (search, status)
POST /                      # Criar ordem manualmente
PUT  /{id}/approve          # Aprovar ordem
PUT  /{id}/reject           # Rejeitar ordem
GET  /{id}                  # Detalhes da ordem
```

### Fornecedores (`/api/suppliers`)

```http
GET    /                    # Lista fornecedores
GET    /{id}                # Detalhes
GET    /{id}/offers         # Ofertas do fornecedor
POST   /                    # Criar fornecedor
PUT    /{id}                # Atualizar
DELETE /{id}                # Deletar
POST   /{id}/offers         # Adicionar oferta
GET    /product/{sku}       # Fornecedores por produto
```

### ML (`/ml`)

```http
POST /train/all/async       # Treinar todos (Celery)
POST /train/{sku}/async     # Treinar um produto (Celery)
POST /train/{sku}           # Treinar síncrono
GET  /predict/{sku}         # Previsão (target, days_ahead)
GET  /models                # Lista modelos treinados
GET  /models/{sku}          # Detalhes do modelo
GET  /models/{sku}/targets  # Targets disponíveis
DELETE /models/{sku}        # Remove modelo
GET  /tasks/{task_id}       # Status da task Celery
```

### RAG (`/api/rag`)

```http
POST /sync                  # Sincroniza produtos → ChromaDB
GET  /status                # Status do índice
POST /query                 # Busca semântica
```

### Auditoria (`/api/audit`)

```http
GET /decisions              # Log de decisões (limit=100)
GET /decisions/{id}         # Detalhes da decisão
GET /stats                  # Estatísticas agregadas
```

---

# 8. MACHINE LEARNING

## 8.1 Previsão de Demanda

**Arquivo:** `app/services/ml_service.py`

**Função:** `get_forecast(product_sku, days_ahead, session)`

**Algoritmo:**
1. Calcula demanda média dos últimos 30 dias
2. Aplica fator de dia da semana (seg-sex: 1.1x, sáb-dom: 0.8x)
3. Gera previsões para N dias futuros

**Timezone:** America/Sao_Paulo (UTC-3)

```python
# Exemplo de output
{
  "sku": "MEC-001",
  "forecast": [
    {"date": "2026-01-15", "demand": 55},
    {"date": "2026-01-16", "demand": 60},
    {"date": "2026-01-17", "demand": 44}  # Sábado
  ],
  "average_demand": 50.0,
  "generated_at": "2026-01-14 16:00:00 -03"
}
```

## 8.2 Previsão de Preço

**Função:** `predict_prices_for_product(sku, days_ahead, session)`

**Algoritmo:**
1. Obtém preço atual do banco
2. Aplica tendência linear com variação controlada (±1%/dia)
3. Limita variação total a ±5%

```python
# Exemplo de output
{
  "sku": "MEC-001",
  "predictions": [
    {"date": "2026-01-15", "price": 101.00},
    {"date": "2026-01-16", "price": 99.00},
    ...
  ],
  "current_price": 100.0,
  "trend": "estável",
  "generated_at": "2026-01-14 16:00:00 -03"
}
```

## 8.3 Treinamento de Modelos

**Arquivo:** `app/ml/training.py`

**Tasks Celery:**
- `train_all_products_task` - Treina todos
- `train_product_model_task` - Treina um SKU

**Parâmetros:**
- `optimize`: Se True, usa Optuna para hiperparâmetros
- `n_trials`: Número de iterações Optuna (10-200)

---

# 9. RAG (Retrieval-Augmented Generation)

## 9.1 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                       RAG PIPELINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────┐   │
│  │ Produtos │───▶│  Embeddings │───▶│     ChromaDB     │   │
│  │  (MySQL) │    │ text-embed. │    │  (Vector Store)  │   │
│  └──────────┘    │    -004     │    └────────┬─────────┘   │
│                  └─────────────┘             │             │
│                                              │             │
│  ┌──────────┐    ┌─────────────┐    ┌───────▼──────────┐   │
│  │  Query   │───▶│  Embedding  │───▶│    Retriever     │   │
│  │ (usuário)│    │             │    │   (top-k=5)      │   │
│  └──────────┘    └─────────────┘    └───────┬──────────┘   │
│                                              │             │
│                                              ▼             │
│                                    ┌──────────────────┐    │
│                                    │     Prompt       │    │
│                                    │   + Contexto     │    │
│                                    └───────┬──────────┘    │
│                                            │              │
│                                            ▼              │
│                                    ┌──────────────────┐    │
│                                    │   Gemini 2.5     │    │
│                                    │     Flash        │    │
│                                    └───────┬──────────┘    │
│                                            ▼              │
│                                    ┌──────────────────┐    │
│                                    │    Resposta      │    │
│                                    └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 9.2 Sincronização

**Função:** `index_product_catalog(db_session)`

**Processo:**
1. Carrega todos produtos do MySQL
2. Cria documentos estruturados com metadados
3. Gera embeddings com Google AI
4. Persiste no ChromaDB em `/data/chroma`

**Formato do documento:**

```
Produto: Rolamento 6205-2RS
SKU: MEC-001
Categoria: Mecânica
Estoque: 45 unidades
Estoque Mínimo: 20 unidades
Preço: R$ 23.50
```

## 9.3 Consulta

**Função:** `query_product_catalog_with_google_rag(query, k=20)`

**Retorna:** Resposta em linguagem natural baseada nos documentos recuperados.

---

# 10. TAREFAS ASSÍNCRONAS

## 10.1 Celery Workers

**Arquivo:** `app/core/celery_app.py`

**Broker:** Redis (`redis://broker:6379/0`)

**Tasks registradas:**

| Task | Arquivo | Função |
|------|---------|--------|
| `execute_agent_analysis` | agent_tasks.py | Executa SupplyChainTeam |
| `train_all_products_task` | ml_tasks.py | Treina todos modelos |
| `train_product_model_task` | ml_tasks.py | Treina um modelo |
| `retrain_global_model_task` | ml_tasks.py | Retreina modelo global |

## 10.2 execute_agent_analysis_task

**Fluxo completo:**

```
1. Recebe (sku, session_id)
2. Chama execute_supply_chain_analysis(sku)
3. Salva resultado em auditoria_decisoes
4. Se session_id:
   a. Formata resposta com format_agent_response()
   b. Salva mensagem no chat
   c. Publica no Redis para WebSocket
5. Retorna resultado
```

---

# 11. FRONTEND

## 11.1 Estrutura

```
FrontEnd/src/
├── components/           # Componentes reutilizáveis
│   ├── ui/              # shadcn/ui components
│   ├── Sidebar.tsx      # Menu lateral
│   ├── Header.tsx       # Cabeçalho
│   └── ...
├── pages/               # Páginas da aplicação
│   ├── Dashboard.tsx    # KPIs e alertas
│   ├── Agents.tsx       # Chat com IA
│   ├── Catalog.tsx      # Catálogo de produtos
│   ├── Orders.tsx       # Ordens de compra
│   ├── Suppliers.tsx    # Fornecedores
│   ├── AuditLog.tsx     # Log de auditoria
│   ├── Settings.tsx     # Configurações
│   ├── Login.tsx        # Autenticação
│   └── Register.tsx     # Cadastro
├── contexts/            # React Context
│   └── AuthContext.tsx  # Estado de autenticação
├── lib/                 # Utilitários
│   └── api.ts          # Cliente Axios
└── App.tsx             # Rotas principais
```

## 11.2 Páginas

| Página | Rota | Descrição |
|--------|------|-----------|
| Dashboard | `/` | KPIs, gráficos, alertas de estoque |
| Agentes | `/agents` | Chat IA com histórico de sessões |
| Catálogo | `/catalog` | Lista produtos, estoque, preços |
| Ordens | `/orders` | Lista/aprova/rejeita ordens |
| Fornecedores | `/suppliers` | CRUD fornecedores e ofertas |
| Auditoria | `/audit` | Log de decisões dos agentes |
| Configurações | `/settings` | Configurações do sistema |

---

# 12. INFRAESTRUTURA DOCKER

## 12.1 Serviços

```yaml
# docker-compose.yml

services:
  api:
    build: .
    ports: ["8000:8000"]
    depends_on: [db, broker]
    volumes: [".:/app", "chroma_data:/data/chroma"]
    
  frontend:
    build: ./FrontEnd
    ports: ["5173:5173"]
    
  db:
    image: mysql:8.0
    ports: ["3306:3306"]
    volumes: ["mysql_data:/var/lib/mysql"]
    
  broker:
    image: redis:7-alpine
    ports: ["6379:6379"]
    
  worker:
    build: .
    command: celery -A app.core.celery_app worker -l INFO
    depends_on: [api, broker]
    
  beat:
    build: .
    command: celery -A app.core.celery_app beat -l INFO
    depends_on: [worker]
```

## 12.2 Volumes

| Volume | Caminho | Conteúdo |
|--------|---------|----------|
| mysql_data | /var/lib/mysql | Banco de dados |
| chroma_data | /data/chroma | Índice vetorial |
| models | /app/models | Modelos ML treinados |

---

# 13. FLUXOS END-TO-END

## 13.1 Fluxo de Chat com Análise

```
┌─────────────────────────────────────────────────────────────────────┐
│ USUÁRIO digita: "Analise compra do produto MEC-001"                 │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND (Agents.tsx)                                               │
│ POST /api/chat/sessions/1/messages { content: "..." }               │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ BACKEND (api_chat_router.py)                                        │
│ post_chat_message() → chat_service.process_user_message()           │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CHAT SERVICE                                                         │
│ 1. add_chat_message() - salva msg usuário                           │
│ 2. extract_entities() - {sku: "MEC-001", intent: "analise_compra"}  │
│ 3. intent == "analise_compra" → handle_supply_chain_analysis()      │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HANDLE SUPPLY CHAIN ANALYSIS                                         │
│ execute_agent_analysis_task.delay(sku="MEC-001", session_id=1)      │
│ Retorna: "🔍 Iniciando análise completa..."                         │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CELERY WORKER (agent_tasks.py)                                       │
│ execute_agent_analysis_task()                                        │
│ 1. execute_supply_chain_analysis(sku)                               │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ AGENT SERVICE → SUPPLY CHAIN TEAM                                    │
│ 1. AnalistaDemanda analisa demanda                                  │
│ 2. ComparadorFornecedor busca ofertas                               │
│ 3. AnalistaLogistico calcula custos                                 │
│ 4. DecisionMaker toma decisão final                                 │
│ Output: {need_restock: true, justification: "...", decision: "..."}│
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CELERY WORKER (continuação)                                          │
│ 1. Salva em auditoria_decisoes                                      │
│ 2. format_agent_response() → Markdown                               │
│ 3. add_chat_message() - salva resposta                              │
│ 4. redis_events.publish_chat_message_sync()                         │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ REDIS PUB/SUB                                                        │
│ Canal: chat:session:1                                               │
│ Mensagem: { session_id: 1, content: "## Análise...", ... }          │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ WEBSOCKET (main.py listener)                                         │
│ Recebe mensagem → websocket_manager.send_message(1, data)           │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND (WebSocket client)                                          │
│ Recebe mensagem → Atualiza estado → Renderiza card de análise       │
└─────────────────────────────────────────────────────────────────────┘
```

---

# 14. CONFIGURAÇÕES

## 14.1 Variáveis de Ambiente

```bash
# .env

# ============ BANCO DE DADOS ============
MYSQL_ROOT_PASSWORD=change_me
MYSQL_DATABASE=app_db
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password
DATABASE_URL=mysql+pymysql://app_user:app_password@db:3306/app_db

# ============ GOOGLE AI ============
GOOGLE_API_KEY=AIzaSy...sua_chave
GOOGLE_GEMINI_MODEL=gemini-2.5-flash

# ============ REDIS ============
REDIS_URL=redis://broker:6379/0

# ============ LLM LOCAL (OPCIONAL) ============
USE_LOCAL_LLM=false
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct

# ============ CELERY ============
CELERY_BROKER_URL=redis://broker:6379/0
CELERY_RESULT_BACKEND=redis://broker:6379/0
```

---

# 15. TROUBLESHOOTING

## 15.1 Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| `GOOGLE_API_KEY not found` | Variável não configurada | Adicionar no .env |
| `ChromaDB instance conflict` | Múltiplas conexões | Usar singleton |
| `Gemini 429 Rate Limit` | Muitas requisições | Aguardar ou usar fallback |
| `Agent returned None` | Falha na API | Verificar logs, retry |
| `function call turn order` | Histórico corrompido | Limpar sessão de chat |
| `Data too long for column` | Texto excede VARCHAR | Alterar para TEXT |

## 15.2 Comandos Úteis

```bash
# Ver logs
docker compose logs -f api
docker compose logs -f worker

# Reiniciar serviço
docker compose restart api

# Limpar sessões de chat
docker compose exec api python3 -c "
from sqlmodel import Session, create_engine
from sqlalchemy import text
engine = create_engine('mysql+pymysql://app_user:app_password@db:3306/app_db')
with Session(engine) as s:
    s.exec(text('SET FOREIGN_KEY_CHECKS=0'))
    s.exec(text('DELETE FROM chat_context'))
    s.exec(text('DELETE FROM chat_messages'))
    s.exec(text('DELETE FROM chat_sessions'))
    s.exec(text('SET FOREIGN_KEY_CHECKS=1'))
    s.commit()
print('OK')
"

# Popular dados demo
docker compose exec api python scripts/seed_demo.py

# Sincronizar RAG
curl -X POST http://localhost:8000/api/rag/sync

# Treinar todos modelos ML
curl -X POST http://localhost:8000/ml/train/all/async
```

---

**Documentação Completa End-to-End**
*Gerada em: 14/01/2026*
*Versão: 1.2.0*
