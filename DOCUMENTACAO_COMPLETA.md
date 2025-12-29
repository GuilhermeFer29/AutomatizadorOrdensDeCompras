# 📚 DOCUMENTAÇÃO COMPLETA DO PROJETO

## 🎯 Automação Inteligente de Ordens de Compra para PMI

**Sistema completo de IA multi-agente para análise e recomendação inteligente de compras industriais.**

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Stack Tecnológico](#stack-tecnológico)
4. [Estrutura do Projeto](#estrutura-do-projeto)
5. [Backend (API FastAPI)](#backend-api-fastapi)
6. [Frontend (React + Vite)](#frontend-react--vite)
7. [Sistema Multi-Agente](#sistema-multi-agente)
8. [Machine Learning](#machine-learning)
9. [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
10. [Banco de Dados](#banco-de-dados)
11. [Configuração e Instalação](#configuração-e-instalação)
12. [API Endpoints](#api-endpoints)
13. [Fluxos de Trabalho](#fluxos-de-trabalho)
14. [Scripts Utilitários](#scripts-utilitários)
15. [Testes](#testes)
16. [Deploy com Docker](#deploy-com-docker)
17. [Variáveis de Ambiente](#variáveis-de-ambiente)
18. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

### Objetivo do Projeto

Este sistema foi desenvolvido para automatizar e otimizar o processo de tomada de decisão em compras industriais para pequenas e médias indústrias (PMI). Utilizando inteligência artificial generativa, machine learning e uma arquitetura multi-agente, o sistema é capaz de:

- **Analisar demanda** e prever necessidades de reposição
- **Comparar fornecedores** considerando preço, confiabilidade e prazo
- **Recomendar compras** com justificativas detalhadas
- **Conversar naturalmente** com usuários para responder dúvidas

### Principais Funcionalidades

| Funcionalidade | Descrição |
|---------------|-----------|
| 🤖 Chat Inteligente | Interface conversacional com IA para consultas |
| 📊 Dashboard Analítico | Visualização de métricas e previsões |
| 📦 Catálogo de Produtos | Gestão completa de produtos e estoque |
| 📋 Ordens de Compra | Criação e aprovação automatizada |
| 🔮 Previsões ML | Previsão de demanda com AutoARIMA |
| 🔍 RAG | Busca semântica no catálogo de produtos |

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                               │
│                    Vite + TypeScript + TailwindCSS + shadcn/ui              │
├─────────────────────────────────────────────────────────────────────────────┤
│  📊 Dashboard  │  🤖 Agents Chat  │  📦 Catalog  │  📋 Orders  │  🔐 Auth   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  📡 Routers    │  🔧 Services    │  🤖 Agents     │  🧠 ML        │  🔐 Auth│
│  - dashboard   │  - chat_service │  - conversational│ prediction   │ security│
│  - ml_router   │  - rag_service  │  - supply_team   │ training     │ JWT     │
│  - agent_router│  - product      │  - tools         │ model_manager│         │
│  - auth_router │  - order        │  - knowledge     │              │         │
└─────────────────────────────────────────────────────────────────────────────┘
                      ↓                    ↓                    ↓
┌──────────────────────┐  ┌─────────────────────┐  ┌────────────────────────────┐
│     MySQL 8.0        │  │     ChromaDB        │  │        Redis               │
│   Banco Principal    │  │    Vector Store     │  │   Broker/Pub-Sub           │
└──────────────────────┘  └─────────────────────┘  └────────────────────────────┘
                                                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CELERY WORKERS                                  │
│            Processamento Assíncrono de Tasks (ML, Análises)                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológico

### Backend

| Tecnologia | Versão | Descrição |
|------------|--------|-----------|
| **Python** | 3.11+ | Linguagem principal |
| **FastAPI** | Latest | Framework web assíncrono |
| **SQLModel** | Latest | ORM moderno (SQLAlchemy + Pydantic) |
| **Agno** | 2.1.3+ | Framework de agentes IA |
| **LangChain** | Latest | Orquestração de LLM para RAG |
| **ChromaDB** | Latest | Vector database para embeddings |
| **Celery** | Latest | Task queue assíncrona |
| **Redis** | 7+ | Message broker e cache |
| **MySQL** | 8.0 | Banco de dados principal |

### Frontend

| Tecnologia | Versão | Descrição |
|------------|--------|-----------|
| **React** | 18.3+ | Biblioteca UI |
| **TypeScript** | 5.8+ | Tipagem estática |
| **Vite** | 7.1+ | Build tool |
| **TailwindCSS** | 3.4+ | Framework CSS |
| **shadcn/ui** | Latest | Componentes UI |
| **Recharts** | 3.2+ | Gráficos |
| **React Query** | 5.8+ | State management |

### IA/ML

| Tecnologia | Versão | Descrição |
|------------|--------|-----------|
| **Google Gemini** | 2.5 Flash | LLM principal |
| **Google AI Embeddings** | text-embedding-004 | Geração de embeddings |
| **StatsForecast** | Latest | Previsão estatística |
| **AutoARIMA** | Latest | Modelo de série temporal |
| **Tavily** | Latest | Web search para agentes |

---

## 📁 Estrutura do Projeto

```
📦 Automação Inteligente de Ordens de Compra/
├── 📂 app/                          # Backend FastAPI
│   ├── 📂 agents/                   # Sistema Multi-Agente
│   │   ├── __init__.py
│   │   ├── conversational_agent.py  # Agente principal (Gerente)
│   │   ├── supply_chain_team.py     # Time de especialistas
│   │   ├── tools.py                 # Ferramentas dos agentes
│   │   ├── knowledge.py             # Base de conhecimento RAG
│   │   └── llm_config.py            # Configuração LLMs
│   ├── 📂 core/                     # Configurações centrais
│   │   ├── database.py              # Conexão MySQL
│   │   ├── security.py              # Autenticação JWT
│   │   ├── celery_app.py            # Configuração Celery
│   │   └── retry_config.py          # Retry logic
│   ├── 📂 ml/                       # Machine Learning
│   │   ├── prediction.py            # Previsões StatsForecast
│   │   ├── training.py              # Treino de modelos
│   │   └── model_manager.py         # Gerência de modelos
│   ├── 📂 models/                   # Modelos de dados
│   │   └── models.py                # SQLModel entities
│   ├── 📂 routers/                  # API Endpoints
│   │   ├── dashboard_router.py      # Dashboard HTML/JSON
│   │   ├── ml_router.py             # Endpoints ML
│   │   ├── agent_router.py          # Endpoints agentes
│   │   ├── auth_router.py           # Autenticação
│   │   ├── api_chat_router.py       # Chat API
│   │   ├── api_product_router.py    # Produtos API
│   │   ├── api_order_router.py      # Ordens API
│   │   └── rag_router.py            # RAG sync endpoints
│   ├── 📂 services/                 # Lógica de negócio
│   │   ├── chat_service.py          # Serviço de chat
│   │   ├── rag_service.py           # Serviço RAG
│   │   ├── rag_sync_service.py      # Sincronização RAG
│   │   ├── hybrid_query_service.py  # Queries híbridas
│   │   ├── product_service.py       # Serviço produtos
│   │   ├── order_service.py         # Serviço ordens
│   │   └── websocket_manager.py     # WebSocket handling
│   ├── 📂 tasks/                    # Celery Tasks
│   │   └── supply_chain_tasks.py
│   ├── 📂 tests/                    # Testes unitários
│   └── main.py                      # Entry point FastAPI
├── 📂 FrontEnd/                     # Interface React
│   ├── 📂 src/
│   │   ├── 📂 components/           # Componentes React
│   │   │   ├── 📂 dashboard/        # Widgets dashboard
│   │   │   ├── 📂 layout/           # Layout comum
│   │   │   └── 📂 ui/               # shadcn/ui components
│   │   ├── 📂 pages/                # Páginas da aplicação
│   │   │   ├── Dashboard.tsx        # Dashboard principal
│   │   │   ├── Agents.tsx           # Chat com agentes
│   │   │   ├── Orders.tsx           # Gestão de ordens
│   │   │   ├── Catalog.tsx          # Catálogo produtos
│   │   │   ├── Login.tsx            # Login
│   │   │   └── Register.tsx         # Registro
│   │   ├── 📂 hooks/                # React hooks customizados
│   │   ├── 📂 services/             # API calls
│   │   ├── 📂 types/                # TypeScript types
│   │   ├── App.tsx                  # Entry point React
│   │   └── main.tsx                 # Bootstrap
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── Dockerfile
├── 📂 scripts/                      # Scripts utilitários
│   ├── seed_database.py             # Popular banco
│   ├── generate_realistic_data.py   # Dados sintéticos
│   ├── sync_vectors.py              # Sincronizar ChromaDB
│   ├── train_all_phases.py          # Treinar modelos
│   └── start_pipeline.py            # Pipeline completo
├── 📂 migrations/                   # Migrations SQL
│   └── add_supplier_market_features.sql
├── 📂 data/                         # Dados (gitignored)
│   └── chroma/                      # Vector store
├── docker-compose.yml               # Orquestração Docker
├── Dockerfile                       # Build API
├── requirements.txt                 # Dependências Python
├── .env                             # Variáveis ambiente (gitignored)
└── README.md                        # Documentação resumida
```

---

## 🔧 Backend (API FastAPI)

### Entry Point (`app/main.py`)

O arquivo principal configura a aplicação FastAPI com:

```python
# Principais configurações
app = FastAPI(
    title="Automação Inteligente de Ordens de Compra",
    description="API para plataforma preditiva de cadeia de suprimentos",
    version="0.1.0",
    lifespan=lifespan,  # Gerencia startup/shutdown
)

# Lifespan events
# - Cria tabelas no banco
# - Inicializa RAG (ChromaDB)
# - Conecta ao Redis para WebSocket

# CORS configurado para desenvolvimento
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Routers registrados
# - /dashboard - Dashboard HTML
# - /ml - Endpoints Machine Learning
# - /agents - Interação com agentes
# - /api/chat - Chat conversacional
# - /api/products - CRUD produtos
# - /api/orders - Ordens de compra
# - /auth - Login/Register
# - /rag - Sincronização RAG
```

### Routers Principais

#### Dashboard Router (`/dashboard`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/dashboard/` | GET | Renderiza dashboard HTML |
| `/dashboard/report` | GET | Gera relatório global |

#### ML Router (`/ml`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/ml/forecast/{sku}` | GET | Previsão para produto |
| `/ml/train` | POST | Treinar modelo |
| `/ml/metrics` | GET | Métricas do modelo |

#### Agent Router (`/agents`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/agents/` | GET | Listar agentes |
| `/agents/status` | GET | Status do time |

#### Chat Router (`/api/chat`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/chat/sessions` | POST | Nova sessão |
| `/api/chat/sessions/{id}/messages` | POST | Enviar mensagem |
| `/api/chat/sessions/{id}/history` | GET | Histórico |

#### Products Router (`/api/products`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/products/` | GET | Listar produtos |
| `/api/products/{id}` | GET | Detalhes produto |
| `/api/products/` | POST | Criar produto |
| `/api/products/{id}` | PUT | Atualizar produto |

#### Orders Router (`/api/orders`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/orders/` | GET | Listar ordens |
| `/api/orders/` | POST | Criar ordem |
| `/api/orders/{id}/approve` | POST | Aprovar ordem |
| `/api/orders/{id}/reject` | POST | Rejeitar ordem |

#### Auth Router (`/auth`)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/auth/login` | POST | Login (JWT) |
| `/auth/register` | POST | Registro |
| `/auth/me` | GET | Usuário atual |

---

## 💻 Frontend (React + Vite)

### Páginas da Aplicação

#### 1. Login (`/login`)
- Formulário de autenticação
- Integração com JWT
- Redirecionamento automático

#### 2. Dashboard (`/`)
- **Cartões de Métricas**: Estoque, vendas, alertas
- **Gráficos**: Previsões de demanda
- **Alertas**: Produtos com estoque baixo

#### 3. Agents (`/agents`)
- **Chat Interativo**: Conversa com IA
- **Histórico**: Mensagens anteriores
- **Markdown**: Renderização rica

#### 4. Orders (`/orders`)
- **Lista de Ordens**: Todas as ordens de compra
- **Status**: Pendente, Aprovada, Rejeitada
- **Ações**: Aprovar/Rejeitar ordens

#### 5. Catalog (`/catalog`)
- **Lista de Produtos**: Catálogo completo
- **Busca**: Filtro por nome/SKU
- **Detalhes**: Modal com informações

### Componentes Principais

```tsx
// Estrutura de componentes
📂 components/
├── 📂 dashboard/
│   ├── DashboardStats.tsx     # Cartões de estatísticas
│   ├── ForecastChart.tsx      # Gráfico de previsões
│   └── AlertsWidget.tsx       # Widget de alertas
├── 📂 layout/
│   ├── MainLayout.tsx         # Layout principal
│   └── Sidebar.tsx            # Menu lateral
└── 📂 ui/                     # shadcn/ui (~50 componentes)
```

### Autenticação Frontend

```tsx
// ProtectedRoute component
const ProtectedRoute = ({ element }) => {
  const token = localStorage.getItem("token");
  return token ? element : <Navigate to="/login" replace />;
};

// Rotas protegidas
<Routes>
  <Route path="/login" element={<Login />} />
  <Route path="/*" element={<ProtectedRoute element={<MainLayout>...</MainLayout>} />} />
</Routes>
```

---

## 🤖 Sistema Multi-Agente

### Arquitetura de Agentes

O sistema utiliza o framework **Agno** para criar uma hierarquia de agentes especializados:

```
┌────────────────────────────────────────────────────────────────────┐
│                    AGENTE CONVERSACIONAL (Gerente)                  │
│                                                                     │
│  Responsabilidades:                                                │
│  • Interface com usuário                                           │
│  • Delegação inteligente                                           │
│  • Respostas rápidas para perguntas simples                        │
└────────────────────────────────────────────────────────────────────┘
                              ↓ Delega
┌────────────────────────────────────────────────────────────────────┐
│                    TIME DE ESPECIALISTAS (4 agentes)               │
├─────────────────┬────────────────┬──────────────────┬──────────────┤
│  1️⃣ ANALISTA   │  2️⃣ PESQUISADOR │  3️⃣ ANALISTA    │  4️⃣ GERENTE  │
│     DEMANDA     │     MERCADO     │    LOGÍSTICA    │    COMPRAS   │
├─────────────────┼────────────────┼──────────────────┼──────────────┤
│ • Avalia        │ • Busca        │ • Avalia         │ • Consolida  │
│   estoque       │   ofertas      │   fornecedores   │   análises   │
│ • Previsão      │ • Tendências   │ • Custo total    │ • Decisão    │
│   de demanda    │   de mercado   │   aquisição      │   final      │
└─────────────────┴────────────────┴──────────────────┴──────────────┘
```

### Agente Conversacional (`conversational_agent.py`)

```python
def get_conversational_agent(session_id: str) -> Agent:
    """Cria o Agente Conversacional usando arquitetura Agno Pura."""
    
    agent = Agent(
        name="PurchaseAssistant",
        model=get_gemini_for_decision_making(),  # Gemini 2.5 Flash
        
        # Base de Conhecimento (RAG)
        knowledge=load_knowledge_base(),
        search_knowledge=True,
        
        # Ferramentas disponíveis
        tools=[
            get_product_info,           # Info do produto
            get_price_forecast_for_sku, # Previsão ML
            find_supplier_offers,       # Ofertas fornecedores
            run_full_purchase_analysis, # Delegação ao time
            create_purchase_order_tool, # Criar ordem
        ],
        
        # Memória persistente
        db=SqliteDb(db_file="data/agent_memory.db"),
        session_id=session_id,
        add_history_to_context=True,
        num_history_messages=5,
    )
    
    return agent
```

### Ferramentas dos Agentes (`tools.py`)

| Ferramenta | Descrição | Retorno |
|------------|-----------|---------|
| `get_product_info(sku)` | Informações do produto | JSON com estoque, preço, etc |
| `get_price_forecast_for_sku(sku, days)` | Previsão de preços | JSON com tendência |
| `find_supplier_offers_for_sku(sku)` | Ofertas de fornecedores | JSON com lista de ofertas |
| `run_full_purchase_analysis(sku, reason)` | Análise completa pelo time | Recomendação em Markdown |
| `create_purchase_order_tool(sku, qty, price, supplier)` | Criar ordem de compra | JSON com ID da ordem |
| `search_market_price(sku)` | Preço de mercado | Preço atual |

### Time de Especialistas (`supply_chain_team.py`)

```python
def create_supply_chain_team() -> Team:
    """Cria o time de análise de cadeia de suprimentos."""
    
    # 1. Analista de Demanda
    demand_analyst = Agent(
        name="DemandAnalyst",
        model=get_gemini_for_fast_agents(),
        instructions=ANALISTA_DEMANDA_PROMPT,
        # Saída: {need_restock: bool, justification: str}
    )
    
    # 2. Pesquisador de Mercado
    market_researcher = Agent(
        name="MarketResearcher",
        model=get_gemini_for_fast_agents(),
        tools=[
            find_supplier_offers_for_sku,
            search_market_trends_for_product,
            get_price_forecast_for_sku,
        ],
        # Saída: {offers: [], market_trends: str}
    )
    
    # 3. Analista de Logística
    logistics_analyst = Agent(
        name="LogisticsOptimizer",
        model=get_gemini_for_fast_agents(),
        tools=[compute_distance],
        # Saída: {best_supplier: str, total_cost: float}
    )
    
    # 4. Gerente de Compras
    purchase_manager = Agent(
        name="PurchaseManager",
        model=get_gemini_for_decision_making(),
        # Saída: {decision: approve|reject, rationale: str}
    )
    
    return Team(
        agents=[demand_analyst, market_researcher, logistics_analyst, purchase_manager],
        mode="coordinate",
        leader=purchase_manager,
    )
```

---

## 🧠 Machine Learning

### Módulo de Previsão (`app/ml/prediction.py`)

O sistema utiliza **StatsForecast** com **AutoARIMA** para previsões de demanda:

```python
def predict_prices_for_product(sku: str, days_ahead: int = 14) -> Dict[str, Any]:
    """
    Gera previsão de demanda usando StatsForecast (AutoARIMA).
    
    Features:
    - Sem necessidade de GPU
    - Auto-tuning de hiperparâmetros
    - Cross-validation para métricas
    - Fallback para Naive se ARIMA falhar
    """
    # 1. Carregar histórico de vendas
    df = _load_history_as_dataframe(session, sku)
    
    # 2. Configurar modelos
    models = [
        AutoARIMA(season_length=7),  # Sazonalidade semanal
        Naive()  # Fallback
    ]
    
    sf = StatsForecast(models=models, freq='D', n_jobs=1)
    
    # 3. Treinar e prever
    sf.fit(df)
    forecast_df = sf.predict(h=days_ahead)
    
    # 4. Retornar resultados
    return {
        "sku": sku,
        "dates": dates,
        "prices": values,  # "prices" por compatibilidade
        "model_used": "StatsForecast_AutoARIMA",
        "metrics": {"mape": mape, "rmse": rmse, "mae": mae}
    }
```

### Métricas Calculadas

| Métrica | Descrição |
|---------|-----------|
| **MAPE** | Mean Absolute Percentage Error |
| **RMSE** | Root Mean Square Error |
| **MAE** | Mean Absolute Error |

---

## 🔍 RAG (Retrieval-Augmented Generation)

### Arquitetura RAG (`app/services/rag_service.py`)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PIPELINE RAG                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INDEXAÇÃO                                                   │
│     Produtos (MySQL) → Embeddings → ChromaDB                    │
│                                                                 │
│  2. CONSULTA                                                    │
│     Pergunta → Embedding → Busca Vetorial → Contexto            │
│                                                                 │
│  3. GERAÇÃO                                                     │
│     Contexto + Prompt → Gemini 2.5 → Resposta                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Configuração

```python
# Embeddings (Google AI)
google_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)

# Vector Store (ChromaDB)
vector_store = Chroma(
    collection_name="product_catalog",
    embedding_function=google_embeddings,
    persist_directory=CHROMA_PERSIST_DIR,
)

# LLM (Gemini 2.5 Flash)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,  # Baixa para respostas factuais
)
```

### Funções Principais

| Função | Descrição |
|--------|-----------|
| `index_product_catalog(session)` | Indexa todos os produtos |
| `query_product_catalog_with_google_rag(query)` | Consulta RAG |
| `get_relevant_context(query, session)` | Obtém contexto relevante |

---

## 🗄️ Banco de Dados

### Modelos SQLModel (`app/models/models.py`)

#### Produto
```python
class Produto(SQLModel, table=True):
    __tablename__ = "produtos"
    
    id: Optional[int] = Field(primary_key=True)
    nome: str = Field(index=True, max_length=255)
    sku: str = Field(unique=True, max_length=50)
    categoria: Optional[str]
    estoque_atual: int = 0
    estoque_minimo: int = 0
    
    # Relacionamentos
    vendas: List["VendasHistoricas"] = Relationship(back_populates="produto")
    precos: List["PrecosHistoricos"] = Relationship(back_populates="produto")
```

#### VendasHistoricas
```python
class VendasHistoricas(SQLModel, table=True):
    __tablename__ = "vendas_historicas"
    
    id: Optional[int] = Field(primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id")
    data_venda: datetime
    quantidade: int
    receita: Decimal
```

#### Fornecedor
```python
class Fornecedor(SQLModel, table=True):
    __tablename__ = "fornecedores"
    
    id: Optional[int] = Field(primary_key=True)
    nome: str
    confiabilidade: float = 0.9  # 0.0 a 1.0
    prazo_entrega_dias: int = 7
```

#### OfertaProduto
```python
class OfertaProduto(SQLModel, table=True):
    __tablename__ = "ofertas_produtos"
    
    id: Optional[int] = Field(primary_key=True)
    produto_id: int
    fornecedor_id: int
    preco_ofertado: Decimal
    estoque_disponivel: int
```

#### OrdemDeCompra
```python
class OrdemDeCompra(SQLModel, table=True):
    __tablename__ = "ordens_de_compra"
    
    id: Optional[int] = Field(primary_key=True)
    produto_id: int
    fornecedor_id: int
    quantidade: int
    preco_unitario: Decimal
    status: str = "pending"  # pending, approved, rejected
    data_criacao: datetime
    data_aprovacao: Optional[datetime]
    justificativa: Optional[str]
```

#### User (Autenticação)
```python
class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = True
    full_name: Optional[str]
```

### Diagrama ER

```
┌─────────────┐       ┌──────────────────┐       ┌────────────────┐
│  produtos   │───────│ vendas_historicas │       │  fornecedores  │
├─────────────┤       ├──────────────────┤       ├────────────────┤
│ id (PK)     │◄──────│ produto_id (FK)  │       │ id (PK)        │
│ nome        │       │ data_venda       │       │ nome           │
│ sku         │       │ quantidade       │       │ confiabilidade │
│ categoria   │       │ receita          │       │ prazo_entrega  │
│ estoque_*   │       └──────────────────┘       └────────────────┘
└─────────────┘                                          │
       │                                                 │
       │         ┌─────────────────┐                     │
       │         │ ofertas_produtos│                     │
       └────────►├─────────────────┤◄────────────────────┘
                 │ produto_id (FK) │
                 │ fornecedor_id   │
                 │ preco_ofertado  │
                 └─────────────────┘
                          │
       ┌──────────────────┴──────────────────┐
       │          ordens_de_compra           │
       ├─────────────────────────────────────┤
       │ id (PK)                             │
       │ produto_id (FK)                     │
       │ fornecedor_id (FK)                  │
       │ quantidade                          │
       │ status (pending/approved/rejected)  │
       └─────────────────────────────────────┘
```

---

## ⚙️ Configuração e Instalação

### Pré-requisitos

- Docker & Docker Compose
- Node.js 18+ (para desenvolvimento frontend)
- Python 3.11+ (para desenvolvimento local)

### Setup Rápido (Docker)

```bash
# 1. Clonar repositório
git clone <repository-url>
cd "Automação Inteligente de Ordens de Compra"

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# 3. Subir containers
docker compose up -d

# 4. Verificar logs
docker compose logs -f api

# 5. Acessar aplicação
# Frontend: http://localhost:3000
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Setup Desenvolvimento (Local)

#### Backend

```bash
# 1. Criar virtualenv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar .env
export GOOGLE_API_KEY=your_key
export DATABASE_URL=mysql+mysqlconnector://user:pass@localhost:3306/db

# 4. Rodar migrações
python scripts/create_tables.py

# 5. Popular banco
python scripts/seed_database.py

# 6. Sincronizar RAG
python scripts/sync_vectors.py

# 7. Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd FrontEnd

# 1. Instalar dependências
npm install
# ou: bun install

# 2. Configurar API
echo "VITE_API_URL=http://localhost:8000" > .env.local

# 3. Iniciar dev server
npm run dev
```

---

## 🔑 Variáveis de Ambiente

### Backend (.env)

```bash
# === OBRIGATÓRIAS ===

# Google AI (Gemini 2.5)
GOOGLE_API_KEY=your_google_api_key

# Database (MySQL)
DATABASE_URL=mysql+mysqlconnector://user:password@db:3306/app_db
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=app_db
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password

# Redis
REDIS_URL=redis://broker:6379/0

# === OPCIONAIS ===

# Tavily (Web Search)
TAVILY_API_KEY=your_tavily_key

# JWT Security
SECRET_KEY=your_secret_key_32_chars
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Celery
CELERY_BROKER_URL=redis://broker:6379/0
CELERY_RESULT_BACKEND=redis://broker:6379/0
```

### Frontend (.env.local)

```bash
VITE_API_URL=http://localhost:8000
```

---

## 📜 Scripts Utilitários

### Scripts Disponíveis (`/scripts`)

| Script | Descrição | Comando |
|--------|-----------|---------|
| `seed_database.py` | Popular banco com produtos | `python scripts/seed_database.py [csv_path]` |
| `generate_realistic_data.py` | Gerar dados sintéticos | `python scripts/generate_realistic_data.py` |
| `sync_vectors.py` | Sincronizar ChromaDB | `python scripts/sync_vectors.py` |
| `train_all_phases.py` | Treinar modelos ML | `python scripts/train_all_phases.py` |
| `start_pipeline.py` | Executar pipeline completo | `python scripts/start_pipeline.py` |
| `test_agent_flow.py` | Testar fluxo de agentes | `python scripts/test_agent_flow.py` |
| `validate_timeseries.py` | Validar séries temporais | `python scripts/validate_timeseries.py` |

### Execução via Docker

```bash
# Popular banco
docker compose exec api python scripts/seed_database.py

# Sincronizar RAG
docker compose exec api python scripts/sync_vectors.py

# Treinar modelos
docker compose exec api python scripts/train_all_phases.py
```

---

## 🧪 Testes

### Estrutura de Testes

```
📂 app/tests/
├── test_agents.py        # Testes de agentes
├── test_ml.py            # Testes de ML
├── test_rag.py           # Testes de RAG
├── test_routers.py       # Testes de endpoints
└── test_services.py      # Testes de serviços
```

### Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=app

# Testes específicos
pytest app/tests/test_agents.py -v
```

---

## 🐳 Deploy com Docker

### Serviços Docker Compose

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| `frontend` | 3000 | React + Nginx |
| `api` | 8000 | FastAPI |
| `worker` | - | Celery Worker |
| `beat` | - | Celery Beat |
| `db` | 3306 | MySQL 8.0 |
| `broker` | 6380 | Redis |

### Comandos Úteis

```bash
# Iniciar todos os serviços
docker compose up -d

# Ver logs
docker compose logs -f api

# Reconstruir imagem
docker compose build api

# Acessar container
docker compose exec api bash

# Parar tudo
docker compose down

# Limpar volumes
docker compose down -v
```

---

## 🔧 Troubleshooting

### Erro: "GOOGLE_API_KEY não encontrada"

```bash
# Verificar se está no .env
cat .env | grep GOOGLE_API_KEY

# Definir manualmente
export GOOGLE_API_KEY=your_key
```

### Erro: "Conexão com banco recusada"

```bash
# Verificar se MySQL está rodando
docker compose logs db

# Aguardar healthcheck
docker compose ps  # Status deve ser "healthy"
```

### Erro: "ChromaDB instance conflict"

```bash
# Limpar dados do ChromaDB
rm -rf data/chroma

# Resincronizar
python scripts/sync_vectors.py
```

### Erro: "Rate limit exceeded" (Google API)

```bash
# Verificar quotas em:
# https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/quotas

# Usar modelo menor temporariamente
# Em llm_config.py, mudar para:
# model="gemini-2.0-flash"
```

### Frontend não conecta na API

```bash
# Verificar CORS
# Em app/main.py, allow_origins deve incluir http://localhost:3000

# Verificar URL da API
# Em FrontEnd/.env.local:
VITE_API_URL=http://localhost:8000
```

---

## 📊 Métricas e Monitoramento

### Health Check

```bash
# Verificar saúde da API
curl http://localhost:8000/health
# {"status": "ok"}
```

### Endpoints de Status

| Endpoint | Descrição |
|----------|-----------|
| `/health` | Status da API |
| `/agents/status` | Status dos agentes |
| `/ml/metrics` | Métricas dos modelos |
| `/rag/status` | Status do ChromaDB |

---

## 🚀 Próximos Passos

1. ✅ **CONCLUÍDO**: Arquitetura multi-agente implementada
2. ✅ **CONCLUÍDO**: Sistema RAG com ChromaDB
3. ✅ **CONCLUÍDO**: Previsões com StatsForecast
4. 🧪 **EM TESTE**: Fluxos end-to-end
5. 📊 **PLANEJADO**: Monitoramento de métricas em produção
6. 🔒 **PLANEJADO**: Rate limiting e segurança avançada
7. 📈 **PLANEJADO**: Dashboard analítico avançado

---

## 📚 Referências

- [Agno Framework](https://docs.agno.com/) - Framework de agentes
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web
- [LangChain](https://python.langchain.com/) - Orquestração LLM
- [ChromaDB](https://docs.trychroma.com/) - Vector database
- [Google Gemini](https://ai.google.dev/) - LLM principal
- [StatsForecast](https://nixtla.github.io/statsforecast/) - Previsões estatísticas
- [SQLModel](https://sqlmodel.tiangolo.com/) - ORM moderno

---

**Versão da Documentação**: 1.0.0  
**Última Atualização**: 28/12/2025  
**Status do Projeto**: ✅ Pronto para Produção

---

*Documentação gerada automaticamente com base na análise completa do código-fonte.*
