# 🏭 PMI — Automação Inteligente de Ordens de Compra

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_2.5-4285F4?style=for-the-badge&logo=google&logoColor=white)

**Plataforma SaaS Multi-Tenant de IA Multi-Agente para Automação de Compras Industriais**

[Funcionalidades](#-funcionalidades) •
[Arquitetura](#-arquitetura) •
[Instalação](#-instalação-rápida) •
[API](#-api-endpoints-54-rotas) •
[Configuração](#-variáveis-de-ambiente) •
[Desenvolvimento](#-desenvolvimento-local)

</div>

---

## 📋 Sobre o Projeto

Plataforma completa de **Inteligência Artificial** para automatizar e otimizar decisões de compra em **Pequenas e Médias Indústrias (PMI)**. Combina uma arquitetura multi-agente com Google Gemini 2.5, Machine Learning para previsões de demanda/preço, RAG (Retrieval-Augmented Generation), e um frontend React moderno — tudo com isolamento multi-tenant (Row-Level Security).

### 🎯 Problema vs. Solução

| Antes | Depois |
|-------|--------|
| ❌ Decisões de compra manuais e lentas | ✅ Chat IA — pergunte em linguagem natural |
| ❌ Sem análise de múltiplos fornecedores | ✅ 4 agentes especializados analisam em paralelo |
| ❌ Sem previsão de demanda/preço | ✅ AutoARIMA + ML com séries temporais |
| ❌ Dados isolados em planilhas | ✅ Dashboard real-time + auditoria completa |
| ❌ Sem rastreabilidade de decisões | ✅ Log de auditoria com justificativa IA |

---

## ✨ Funcionalidades

| Módulo | Descrição | Stack |
|--------|-----------|-------|
| 🤖 **Chat IA** | Converse em linguagem natural para obter recomendações | Agno + Gemini 2.5 |
| 📊 **Dashboard** | KPIs, alertas de estoque baixo, métricas em tempo real | React + Recharts |
| 📦 **Catálogo** | CRUD de produtos com estoque, preços e fornecedores | SQLModel + MySQL |
| 📋 **Ordens de Compra** | Crie, aprove ou rejeite com rastreabilidade | FastAPI + Celery |
| 🚚 **Fornecedores** | Gestão completa com ofertas e confiabilidade | Multi-Tenant RLS |
| 📝 **Auditoria** | Histórico completo de decisões dos agentes | Audit Log |
| 🔮 **Previsão ML** | Demanda (AutoARIMA) e preço (StatsForecast) | AutoARIMA + scikit-learn |
| 🔍 **RAG** | Busca semântica inteligente no catálogo | ChromaDB + LangChain |
| 🔄 **Fallback AI** | Alternância automática entre modelos Gemini | gemini-2.5-flash → lite → pro |
| 📈 **Observabilidade** | Métricas Prometheus + Grafana + custo LLM | Prometheus + Grafana |
| 🔐 **Multi-Tenant** | Isolamento completo por empresa (JWT + RLS) | ContextVar + Middleware |
| 🔑 **Credential Store** | Armazenamento criptografado de secrets (Fernet) | cryptography |
| 🔌 **Integrações** | Framework extensível para ERPs (Bling, SAP…) | BaseConnector ABC |

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│               FRONTEND  (React 18 + Vite 7 + TypeScript)           │
│     TailwindCSS • shadcn/ui • Recharts • React Query v5 • Zod     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP / REST / WebSocket
┌──────────────────────────────────┴──────────────────────────────────┐
│                     BACKEND  (FastAPI 0.128)                        │
│                 54 endpoints • Multi-Tenant • JWT                   │
├────────────┬────────────┬────────────┬──────────┬───────────────────┤
│  Routers   │  Services  │   Agents   │    ML    │   Integrations   │
│ (14 files) │ (15 files) │ (Agno 2.4) │ (ARIMA)  │  (BaseConnector) │
└─────┬──────┴─────┬──────┴──────┬─────┴────┬─────┴───────────────────┘
      │            │             │          │
┌─────┴──┐  ┌─────┴──┐   ┌─────┴──┐  ┌────┴──────┐  ┌──────────┐
│ MySQL  │  │ Redis  │   │ Gemini │  │ ChromaDB  │  │ RabbitMQ │
│  8.0   │  │   7    │   │  2.5   │  │ (Vetores) │  │  3.13    │
└────────┘  └────────┘   └────────┘  └───────────┘  └──────────┘
```

### 🤖 Sistema Multi-Agente (Agno Team)

```
                     ┌───────────────────────────────┐
                     │     AGENTE CONVERSACIONAL      │
                     │    (RAG + Reasoning Tools)     │
                     │   Interface com o Usuário      │
                     └──────────────┬────────────────┘
                                    │ Delega via Team
         ┌──────────────┬───────────┴──────────┬──────────────┐
         ↓              ↓                      ↓              ↓
┌─────────────────┐ ┌──────────────────┐ ┌────────────────┐ ┌────────────────┐
│   Analista de   │ │  Pesquisador de  │ │   Analista de  │ │   Gerente de   │
│    Demanda      │ │     Mercado      │ │   Logística    │ │    Compras     │
├─────────────────┤ ├──────────────────┤ ├────────────────┤ ├────────────────┤
│ output_schema:  │ │ output_schema:   │ │ output_schema: │ │ output_schema: │
│ DemandAnalysis  │ │ MarketResearch   │ │ Logistics      │ │ Purchase       │
│                 │ │                  │ │ Analysis       │ │ Recommendation │
│ • Estoque       │ │ • Ofertas        │ │ • Fornecedor   │ │ • Consolida    │
│ • Previsão ML   │ │ • Tendências     │ │ • Custo total  │ │ • Decisão      │
│ • Confiança     │ │ • Previsão ML    │ │ • Alternativas │ │ • Riscos       │
└─────────────────┘ └──────────────────┘ └────────────────┘ └────────────────┘
         ↑                    ↑                   ↑
    Tools: get_forecast  find_supplier_offers  search_market_price
```

**Destaques da arquitetura de agentes:**

- **`output_schema`** (Pydantic) para respostas estruturadas — sem regex/parsing manual
- **`role`** em cada agente para delegação inteligente pelo Team leader
- **Fallback chain:** `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-2.5-pro`
- **Prompts externalizados** em YAML (`app/agents/prompts/`)
- **Métricas de custo LLM** via Prometheus (`llm_metrics.py`)

---

## 🛠️ Stack Tecnológico

### Backend

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Python** | 3.12 | Linguagem principal |
| **FastAPI** | 0.128 | Framework web assíncrono |
| **SQLModel** | 0.0.32 | ORM (SQLAlchemy + Pydantic) |
| **Agno** | 2.4.8 | Framework de agentes IA |
| **LangChain** | 1.2.9 | Orquestração RAG |
| **Celery** | 5.6.2 | Task queue assíncrona |
| **Pydantic Settings** | — | Configuração tipada via env vars |
| **Alembic** | — | Migrations de banco de dados |

### Frontend

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **React** | 18.3 | Biblioteca UI |
| **TypeScript** | 5.8 | Tipagem estática |
| **Vite** | 7.1 | Build tool |
| **TailwindCSS** | 3.4 | Estilização |
| **shadcn/ui** (Radix) | — | Componentes acessíveis |
| **React Query** | 5.83 | Data fetching + cache |
| **Recharts** | 3.2 | Gráficos/dashboards |
| **Zod** | 3.25 | Validação de formulários |
| **React Router** | 6.30 | Roteamento SPA |

### IA / ML

| Tecnologia | Uso |
|------------|-----|
| **Google Gemini 2.5 Flash** | LLM principal (fallback: flash-lite → pro) |
| **gemini-embedding-001** | Embeddings para RAG |
| **ChromaDB** 1.4 | Vector store |
| **StatsForecast** 2.0 (AutoARIMA) | Previsão de demanda e preço |
| **scikit-learn** | Modelos complementares |

### Infraestrutura (Docker Compose — 10 serviços)

| Serviço | Imagem | Porta |
|---------|--------|-------|
| **Frontend** | Nginx (build Vite) | 3000 |
| **API** | python:3.11-slim | 8000 |
| **Worker** | Celery (mesmo image) | — |
| **Beat** | Celery Beat (scheduler) | — |
| **MySQL** | mysql:8.0 | — (interna) |
| **Redis** | redis:7-alpine | — (interna) |
| **RabbitMQ** | rabbitmq:3.13-management | — (interna) |
| **Prometheus** | prom/prometheus:v2.53 | 9095 |
| **Grafana** | grafana/grafana:11.1 | 3001 |
| **Flower** | mher/flower:2.0 | 5555 |

---

## 🚀 Instalação Rápida

### Pré-requisitos

- **Docker** & **Docker Compose** v2+
- **Chave API do Google** (Gemini) — [obter aqui](https://aistudio.google.com/app/apikey)

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/automatizador-ordens-compra.git
cd automatizador-ordens-compra
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com os valores **mínimos obrigatórios**:

```env
# Obrigatório — Google Gemini
GOOGLE_API_KEY=sua_chave_google_api

# Obrigatório — Banco de dados
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=app_db
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password

# Obrigatório — Segurança (gerar chave forte!)
SECRET_KEY=<saída de: python3 -c "import secrets; print(secrets.token_hex(32))">

# Opcional — Busca web de preços
TAVILY_API_KEY=sua_chave_tavily
```

> 📌 Obtenha sua chave Google em: https://aistudio.google.com/app/apikey

### 3. Inicie os containers

```bash
# Todos os serviços (backend + frontend + banco + filas + monitoring)
docker compose up -d

# Ou sem monitoring (mais leve para dev)
docker compose up -d frontend api worker beat db redis rabbitmq
```

### 4. Popule o banco de dados

```bash
# Criar dados de exemplo (produtos, fornecedores, vendas)
docker compose exec api python scripts/seed_database.py

# Sincronizar RAG (indexar produtos no ChromaDB)
docker compose exec api python scripts/sync_vectors.py
```

### 5. Acesse a aplicação

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| 🌐 **Frontend** | http://localhost:3000 | Crie em `/register` |
| ⚡ **API Docs (Swagger)** | http://localhost:8000/docs | — |
| 📖 **API Docs (ReDoc)** | http://localhost:8000/redoc | — |
| 📊 **Grafana** | http://localhost:3001 | admin / admin |
| 🌸 **Flower (Celery)** | http://localhost:5555 | admin / admin |
| 📈 **Prometheus** | http://localhost:9095 | — |

---

## 📖 Como Usar

### 1. Criar uma conta

Acesse http://localhost:3000/register — cada conta cria um **tenant** isolado com seus próprios dados.

### 2. Conversar com o Agente

Na página **Agents**, faça perguntas:

**Perguntas simples (resposta direta via RAG):**

```
"Qual o estoque do SKU_001?"
"Me mostre produtos com estoque baixo"
"Previsão de preço para SKU_001 nos próximos 7 dias?"
```

**Perguntas complexas (análise pelo time de 4 agentes):**

```
"Devo comprar o produto SKU_001?"
"Qual fornecedor é melhor para parafusos?"
"Analise a necessidade de reposição para SKU_001"
```

### 3. Exemplo de Resposta

```
✅ Recomendo APROVAR a compra de 100 unidades

📦 Fornecedor Recomendado: Distribuidora Nacional
   💰 Preço: R$ 1.450,00 (R$ 14,50/un)
   ⏱️ Prazo: 5 dias úteis
   ⭐ Confiabilidade: 95%

📊 Justificativa:
   • Estoque atual (45 un) abaixo do mínimo (80 un)
   • Previsão ML indica tendência de alta (+3%)
   • Melhor custo-benefício entre 5 fornecedores

📋 Próximos passos:
   1. Emitir ordem de compra
   2. Agendar entrega para +5 dias
```

---

## 📡 API Endpoints (54 rotas)

### Autenticação — `/auth`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/auth/register` | Criar conta (tenant + owner) |
| POST | `/auth/login` | Login → JWT com `tenant_id` |
| GET | `/auth/me` | Dados do usuário autenticado |

### Chat IA — `/api/chat`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/chat/sessions` | Listar sessões com preview |
| POST | `/api/chat/sessions` | Criar nova sessão |
| DELETE | `/api/chat/sessions/{id}` | Apagar sessão + mensagens |
| GET | `/api/chat/sessions/{id}/messages` | Histórico de mensagens |
| POST | `/api/chat/sessions/{id}/messages` | Enviar mensagem → resposta IA |
| POST | `/api/chat/sessions/{id}/actions` | Executar ação interativa |
| WS | `/api/chat/ws/{id}` | WebSocket real-time (autenticado) |

### Produtos — `/api/products`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/products/` | Listar (filtros: busca, preço, fornecedor) |
| GET | `/api/products/{id}` | Detalhes do produto |
| POST | `/api/products/` | Criar produto (+ sync RAG automático) |
| PUT | `/api/products/{id}` | Atualizar produto (+ sync RAG automático) |
| GET | `/api/products/{sku}/price-history` | Histórico de preços |

### Ordens de Compra — `/api/orders`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/orders/` | Listar ordens (com cache) |
| POST | `/api/orders/` | Criar ordem |
| POST | `/api/orders/{id}/approve` | Aprovar |
| POST | `/api/orders/{id}/reject` | Rejeitar |

### Fornecedores — `/api/suppliers`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/suppliers/` | Listar com estatísticas |
| GET | `/api/suppliers/{id}` | Detalhes |
| GET | `/api/suppliers/{id}/offers` | Ofertas do fornecedor |
| POST | `/api/suppliers/` | Criar |
| PUT | `/api/suppliers/{id}` | Atualizar |
| DELETE | `/api/suppliers/{id}` | Remover |

### Auditoria — `/api/audit`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/audit/decisions/` | Decisões recentes da IA |
| GET | `/api/audit/decisions/{id}` | Detalhes da decisão |
| GET | `/api/audit/stats/` | Estatísticas de auditoria |

### Dashboard — `/api/dashboard`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/dashboard/kpis` | KPIs principais (cache) |
| GET | `/api/dashboard/alerts` | Alertas de estoque/preço (cache) |

### Machine Learning — `/ml`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/ml/train/all/async` | Treinar todos (Celery async) |
| POST | `/ml/train/{sku}/async` | Treinar modelo de 1 SKU (async) |
| POST | `/ml/train/{sku}` | Treinar síncrono |
| GET | `/ml/predict/{sku}` | Previsão multi-target |
| GET | `/ml/models` | Listar modelos treinados |
| GET | `/ml/models/{sku}` | Info do modelo |
| GET | `/ml/models/{sku}/targets` | Targets disponíveis |
| DELETE | `/ml/models/{sku}` | Deletar modelo |
| GET | `/ml/tasks/{task_id}` | Status da task Celery |

### Agentes — `/agents` + `/api/agents`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/agents/execute-analysis/{sku}` | Análise supply-chain completa |
| GET | `/api/agents/` | Listar agentes |
| POST | `/api/agents/{id}/{action}` | Ativar / pausar / executar |

### RAG — `/api/rag`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/rag/status` | Status do vector store |
| POST | `/api/rag/sync` | Sincronizar incrementalmente |
| POST | `/api/rag/resync` | Re-sync completo |

### Admin — `/admin` (requer role `admin` ou `owner`)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/admin/rag/sync` | Sync RAG (background task) |
| GET | `/admin/rag/status` | Status da sincronização |
| GET | `/admin/health` | Health check detalhado (DB + vector store) |
| POST | `/admin/cache/clear` | Limpar caches Redis |

### Vendas — `/vendas`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/vendas/upload` | Upload CSV de vendas |
| POST | `/vendas/retrain/{produto_id}` | Retreinar modelo |

### Tasks — `/tasks`

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/tasks/{task_id}` | Status de task Celery |

---

## 🔐 Variáveis de Ambiente

> Todas as variáveis estão documentadas em [.env.example](.env.example).

### Obrigatórias

| Variável | Descrição |
|----------|-----------|
| `GOOGLE_API_KEY` | Chave API do Google Gemini (LLM + embeddings) |
| `MYSQL_ROOT_PASSWORD` | Senha root do MySQL |
| `MYSQL_DATABASE` | Nome do banco de dados (ex: `app_db`) |
| `MYSQL_USER` | Usuário do banco |
| `MYSQL_PASSWORD` | Senha do usuário |
| `SECRET_KEY` | Chave JWT — mínimo 32 caracteres |

### Opcionais

| Variável | Default | Descrição |
|----------|---------|-----------|
| `APP_ENV` | `development` | Ambiente (`development` / `staging` / `production`) |
| `TAVILY_API_KEY` | — | Web search para preços externos |
| `REDIS_URL` | `redis://redis:6379/0` | URL do Redis |
| `CELERY_BROKER_URL` | `amqp://pmi:secret@rabbitmq/pmi` | URL do RabbitMQ |
| `PROMETHEUS_ENABLED` | `true` | Habilitar métricas Prometheus |
| `CORS_ALLOW_ALL` | `false` | Liberar todos os CORS (**dev only!**) |
| `FRONTEND_URL` | `http://localhost:5173` | URL do frontend (CORS) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modelo Gemini padrão |
| `SCRAPERAPI_KEY` | — | Chave ScraperAPI (scraping Mercado Livre) |
| `CREDENTIAL_ENCRYPTION_KEY` | — | Chave Fernet para credential store |
| `GRAFANA_USER` / `GRAFANA_PASSWORD` | admin / admin | Credenciais Grafana |
| `FLOWER_USER` / `FLOWER_PASSWORD` | admin / admin | Credenciais Flower UI |

---

## 📂 Estrutura do Projeto

```
📦 AutomacaoPMI/
├── 📂 app/                         # Backend FastAPI
│   ├── main.py                     # Entry point + lifespan + middlewares
│   ├── 📂 agents/                  # Sistema Multi-Agente (Agno)
│   │   ├── conversational_agent.py # Agente de chat (RAG + Reasoning)
│   │   ├── supply_chain_team.py    # Team: 4 agentes especializados
│   │   ├── gemini_fallback.py      # Fallback chain automático
│   │   ├── knowledge.py            # ChromaDB knowledge base
│   │   ├── llm_config.py           # Factory de modelos Gemini
│   │   ├── llm_metrics.py          # Prometheus: custo por chamada LLM
│   │   ├── models.py               # Pydantic output_schema models
│   │   ├── tools_secure.py         # Tools tenant-aware
│   │   └── 📂 prompts/             # Prompts externalizados em YAML
│   ├── 📂 core/                    # Infraestrutura
│   │   ├── config.py               # Pydantic Settings (env vars)
│   │   ├── database.py             # SQLAlchemy sync + async engines
│   │   ├── security.py             # JWT + password hashing
│   │   ├── tenant.py               # Multi-Tenant middleware (JWT)
│   │   ├── tenant_context.py       # ContextVar Row-Level Security
│   │   ├── permissions.py          # RBAC (require_role)
│   │   ├── credential_store.py     # Fernet encrypted secrets
│   │   ├── celery_app.py           # Celery + RabbitMQ + DLQ
│   │   ├── cache.py                # Redis cache (fastapi-cache2)
│   │   └── vector_db.py            # ChromaDB singleton manager
│   ├── 📂 models/                  # SQLModel ORM
│   │   ├── models.py               # Produto, Fornecedor, Ordem, etc.
│   │   └── integration_models.py   # Integration + Credential models
│   ├── 📂 routers/                 # 14 router files → 54 endpoints
│   ├── 📂 services/                # 15 service files (lógica de negócio)
│   ├── 📂 ml/                      # Machine Learning
│   │   ├── training.py             # Treinamento (AutoARIMA, etc.)
│   │   ├── prediction.py           # Previsões multi-target
│   │   └── model_manager.py        # Persistência de modelos (joblib)
│   ├── 📂 tasks/                   # Celery tasks
│   │   ├── agent_tasks.py          # Tasks de agentes
│   │   └── ml_tasks.py             # Tasks de ML (treinamento async)
│   └── 📂 integrations/            # Conectores ERP (extensível)
│       ├── __init__.py             # Registry + factory pattern
│       └── base.py                 # BaseConnector ABC
├── 📂 FrontEnd/                    # React + Vite + TypeScript
│   └── 📂 src/pages/              # 11 páginas
│       ├── Dashboard.tsx           # KPIs + gráficos
│       ├── Agents.tsx              # Chat IA
│       ├── Catalog.tsx             # Produtos
│       ├── Orders.tsx              # Ordens de compra
│       ├── Suppliers.tsx           # Fornecedores
│       ├── AuditLog.tsx            # Log de auditoria
│       ├── Settings.tsx            # Configurações do sistema
│       ├── Login.tsx               # Login
│       ├── Register.tsx            # Registro de conta
│       └── Index.tsx               # Página inicial
├── 📂 scripts/                     # 14 scripts utilitários
│   ├── seed_database.py            # Popular banco de exemplo
│   ├── sync_vectors.py             # Indexar RAG no ChromaDB
│   ├── generate_realistic_data.py  # Dados sintéticos
│   ├── seed_sales_history.py       # Histórico de vendas
│   ├── train_all_phases.py         # Treinar todos os modelos ML
│   └── ...
├── 📂 migrations/                  # Alembic migrations
│   ├── env.py                      # Config de migração
│   └── script.py.mako              # Template de migration
├── 📂 config/                      # Configs de observabilidade
│   ├── prometheus.yml
│   └── 📂 grafana/                 # Dashboards + provisioning
├── docker-compose.yml              # 10 serviços (prod-ready)
├── docker-compose.production.yml   # Override para produção
├── Dockerfile                      # Build da API (python:3.11-slim)
├── requirements.txt                # ~50 dependências Python
├── alembic.ini                     # Config Alembic
├── pyproject.toml                  # Metadados do projeto
└── conftest.py                     # Fixtures de teste (pytest)
```

---

## 🔧 Comandos Úteis

### Docker

```bash
# Iniciar todos os serviços
docker compose up -d

# Escalar workers horizontalmente
docker compose up -d --scale worker=3

# Ver logs da API em tempo real
docker compose logs -f api

# Parar tudo
docker compose down

# Reconstruir imagem (após mudar requirements.txt ou Dockerfile)
docker compose build --no-cache api
```

### Scripts de Dados

```bash
# Popular banco com dados de exemplo
docker compose exec api python scripts/seed_database.py

# Sincronizar RAG (produtos → ChromaDB)
docker compose exec api python scripts/sync_vectors.py

# Gerar dados sintéticos realistas
docker compose exec api python scripts/generate_realistic_data.py

# Gerar histórico de vendas
docker compose exec api python scripts/seed_sales_history.py

# Treinar todos os modelos ML
docker compose exec api python scripts/train_all_phases.py

# Validar séries temporais
docker compose exec api python scripts/validate_timeseries.py
```

### Alembic (Migrations)

```bash
# Gerar migration a partir das mudanças nos models
docker compose exec api alembic revision --autogenerate -m "descrição"

# Aplicar migrations pendentes
docker compose exec api alembic upgrade head

# Reverter última migration
docker compose exec api alembic downgrade -1
```

---

## 💻 Desenvolvimento Local

### Backend

```bash
# Criar e ativar venv
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install --upgrade pip
pip install -r requirements.txt

# Rodar API (precisa de MySQL, Redis, RabbitMQ rodando)
uvicorn app.main:app --reload --port 8000

# Rodar Worker Celery
celery -A app.core.celery_app.celery_app worker --loglevel=info -Q default,ml

# Rodar testes
pytest --cov=app -v
```

### Frontend

```bash
cd FrontEnd

# Instalar dependências
bun install   # ou npm install

# Dev server (http://localhost:5173)
bun dev       # ou npm run dev

# Build produção
bun run build

# Testes
bun test
```

### Variáveis necessárias para dev local

Exporte no terminal ou crie um `.env` na raiz:

```bash
export GOOGLE_API_KEY="sua_chave"
export DATABASE_URL="mysql+pymysql://app_user:app_password@localhost:3306/app_db"
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export APP_ENV="development"
export ALLOW_DEV_CORS="true"
```

---

## 🐛 Troubleshooting

### "GOOGLE_API_KEY não encontrada"

```bash
grep GOOGLE_API_KEY .env                         # Verificar se está no .env
docker compose down && docker compose up -d      # Recriar containers
```

### "Conexão com banco recusada"

```bash
docker compose logs -f db      # Aguardar MySQL iniciar (~30s)
docker compose ps              # Verificar status dos containers
```

### "ChromaDB instance conflict"

```bash
docker compose exec api python scripts/sync_vectors.py   # Resync
# Ou forçar reset do volume:
docker compose down -v         # ⚠️ Remove TODOS os volumes
docker compose up -d
```

### "externally-managed-environment" (pip)

```bash
# Causa: pip tentando instalar no Python do sistema (PEP 668)
# Solução: usar venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend não conecta na API

```bash
# Deve ter VITE_API_URL no FrontEnd/.env.local
echo "VITE_API_URL=http://localhost:8000" > FrontEnd/.env.local
```

---

## 🗺️ Roadmap

- [x] Sistema Multi-Agente com Agno (Team + `output_schema`)
- [x] RAG com ChromaDB + LangChain + `gemini-embedding-001`
- [x] Previsões ML com StatsForecast (AutoARIMA)
- [x] Frontend React completo (11 páginas)
- [x] Autenticação JWT + Multi-Tenant (Row-Level Security)
- [x] RBAC (admin, owner, user)
- [x] Fallback automático de modelos Gemini (2.5-flash → lite → pro)
- [x] Métricas de custo LLM (Prometheus)
- [x] Credential store criptografado (Fernet)
- [x] DLQ (Dead Letter Queue) no Celery / RabbitMQ
- [x] Alembic migrations
- [x] Prompts externalizados em YAML
- [x] WebSocket autenticado (JWT)
- [x] Observabilidade (Prometheus + Grafana + Flower)
- [ ] Conectores ERP reais (Bling, Tiny, SAP Business One)
- [ ] App mobile (React Native)
- [ ] Deploy em cloud (AWS / GCP)
- [ ] Testes E2E (Playwright)

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para detalhes.

