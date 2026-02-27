# 🏭 PMI — Automação Inteligente de Compras Industriais

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-4285F4?logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red)

**Plataforma SaaS multi-tenant que automatiza o ciclo completo de compras industriais utilizando agentes de IA, machine learning para previsão de preços/demanda e RAG para consulta inteligente de catálogo.**

[Funcionalidades](#-funcionalidades) • [Arquitetura](#-arquitetura) • [Setup Rápido](#-setup-rápido) • [Documentação da API](#-documentação-da-api) • [Stack Técnica](#-stack-técnica) • [Métricas](#-métricas)

</div>

---

## 📋 Funcionalidades

### 🤖 Agentes de IA (Multi-Agent Supply Chain Team)
- **Assistente de Compras** — interface conversacional principal com chat em tempo real (WebSocket)
- **Analista de Demanda** — avalia estoque, identifica necessidade de reposição e analisa padrões de consumo
- **Pesquisador de Mercado** — inteligência de mercado, comparação de preços e ofertas de fornecedores
- **Analista de Logística** — otimização logística, custo total e ranking de fornecedores
- **Gerente de Compras** — síntese final e decisão de compra com auditoria completa

### 📊 Machine Learning
- **Previsão de preços** com AutoARIMA (StatsForecast) — forecasting de séries temporais
- **Treinamento automático** via Celery Beat (cron diário às 01:00 UTC)
- **Métricas de modelo** — MAPE, RMSE, MAE por SKU
- **API de previsão** — endpoint REST para consultar previsões por SKU

### 🔍 RAG (Retrieval-Augmented Generation)
- **ChromaDB** como vector store para catálogo de produtos
- **Google Gemini Embeddings** para representação vetorial
- **LangChain** pipeline para busca semântica + resposta contextualizada
- **Sincronização automática** MySQL → ChromaDB

### 🏢 Multi-Tenancy
- **Row-Level Security** via `TenantMixin` em todas as tabelas de dados
- **Isolamento por JWT** — `tenant_id` extraído do token e propagado via `ContextVar`
- **Cache isolado** — chaves Redis por tenant
- **Agentes isolados** — cada tenant tem seu próprio conjunto de dados

### 📈 Dashboard & Monitoramento
- **KPIs em tempo real** — economia gerada, ordens automatizadas, nível de estoque, acurácia ML
- **Alertas de estoque** com ação direta para análise via agente
- **Gráficos de previsão** com comparativo histórico vs. previsão ML
- **Status dos agentes** com controles de ativação/pausa
- **Prometheus + Grafana** para métricas de infraestrutura e LLM

### 🛒 Gestão Operacional
- **Catálogo de produtos** com histórico de preços e previsões
- **Ordens de compra** com workflow de aprovação/rejeição
- **Fornecedores** com métricas de confiabilidade e ofertas
- **Auditoria completa** de todas as decisões dos agentes com raciocínio

---

## 🏗 Arquitetura

```
┌──────────────────┐     ┌───────────────────────────────────────────────────────┐
│    Frontend      │     │                     Backend                           │
│  React + Vite    │────▶│  FastAPI (uvicorn)                                    │
│  nginx :3000     │     │   ├── Middleware: Prometheus → Tenant → CORS          │
└──────────────────┘     │   ├── 15 Routers (52 endpoints) → Services → MySQL   │
                         │   ├── AI Agents (Agno + Gemini 2.5) → ChromaDB (RAG) │
                         │   ├── ML Pipeline (StatsForecast/AutoARIMA)          │
                         │   └── WebSocket Manager → Redis Pub/Sub              │
                         └─────────┬────────────┬────────────┬──────────────────┘
                                   │            │            │
                         ┌─────────▼──┐ ┌───────▼──────┐ ┌──▼──────────┐
                         │ MySQL 8.0  │ │  Redis 7     │ │ RabbitMQ    │
                         │ 20 tabelas │ │ Cache+PubSub │ │ (Broker)    │
                         └────────────┘ └──────────────┘ └──────┬──────┘
                                                                │
                         ┌──────────────────────────────────────▼──────────┐
                         │  Celery Workers (agents + ml queues)            │
                         │  Celery Beat (re-treinamento diário cron)       │
                         └─────────────────────────────────────────────────┘

         Observabilidade: Prometheus :9095 → Grafana :3001 │ Flower :5555
```

### Fluxo de Dados
1. **Request** → TenantMiddleware (extrai `tenant_id` do JWT) → Router → Service → MySQL
2. **Chat** → WebSocket → Agente Conversacional (Agno + Gemini) → Tools (DB queries, RAG, ML) → Resposta em tempo real
3. **Análise Completa** → Celery Task → Supply Chain Team (4 analistas + 1 gerente) → Decisão auditada → Redis Pub/Sub → WebSocket → Frontend
4. **ML Pipeline** → Celery Beat (01:00 UTC) → PrecosHistoricos → StatsForecast/AutoARIMA → Métricas salvas

---

## 🚀 Setup Rápido

### Pré-requisitos
- Docker & Docker Compose v2
- Chave de API do Google Gemini (`GOOGLE_API_KEY`)

### 1. Clone e configure

```bash
git clone <repo-url>
cd AutomacaoPMI
```

### 2. Configure as variáveis de ambiente

Crie o arquivo `.env` na raiz:

```env
# IA
GOOGLE_API_KEY=sua_chave_gemini_aqui

# Banco de Dados
DATABASE_URL=mysql+pymysql://app_user:app_password@db:3306/app_db
ASYNC_DATABASE_URL=mysql+aiomysql://app_user:app_password@db:3306/app_db
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=app_db
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password

# Segurança
SECRET_KEY=sua_chave_secreta_jwt_aqui

# Message Queue
RABBITMQ_DEFAULT_USER=pmi_user
RABBITMQ_DEFAULT_PASS=pmi_password
CELERY_BROKER_URL=amqp://pmi_user:pmi_password@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Redis
REDIS_URL=redis://redis:6379/0

# ChromaDB
CHROMA_PERSIST_DIRECTORY=/data/chroma
```

### 3. Suba todos os serviços

```bash
docker compose up -d --build
```

### 4. Popule o banco de dados

```bash
docker compose exec api python scripts/seed_full.py
```

Isso cria: **50 produtos** (estofaria/ferragens), **10 fornecedores**, **159+ ofertas**, **18.250 registros de preços**, **18.250 registros de vendas**, **40 ordens de compra**, **6 agentes** e um **usuário admin**.

### 5. Acesse

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | `admin@pmi.com.br` / `SeedAdmin1` |
| **API Docs (Swagger)** | http://localhost:8000/docs | — |
| **Grafana** | http://localhost:3001 | admin / admin |
| **Flower (Celery)** | http://localhost:5555 | — |
| **RabbitMQ Management** | http://localhost:15672 | pmi_user / pmi_password |

### 6. Execute os testes

```bash
# Backend (180 testes E2E)
docker compose exec api pytest -v

# Com cobertura
docker compose exec api pytest --cov=app --cov-report=html
```

---

## 📡 Documentação da API

A documentação interativa completa está disponível em `http://localhost:8000/docs` (Swagger UI) e `http://localhost:8000/redoc` (ReDoc).

### Autenticação (`/auth`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/auth/register` | Registro de novo usuário + tenant |
| `POST` | `/auth/login` | Login (OAuth2 password flow) |
| `GET` | `/auth/me` | Dados do usuário autenticado |

### Dashboard (`/api/dashboard`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/dashboard/kpis` | KPIs em tempo real (economia, automação, estoque, ML) |
| `GET` | `/api/dashboard/alerts` | Alertas de produtos com estoque baixo |

### Produtos (`/api/products`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/products/` | Listar todos os produtos |
| `GET` | `/api/products/{id}` | Detalhes de um produto |
| `POST` | `/api/products/` | Criar produto |
| `PUT` | `/api/products/{id}` | Atualizar produto |
| `GET` | `/api/products/{sku}/price-history` | Histórico de preços por SKU |

### Ordens de Compra (`/api/orders`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/orders/` | Listar ordens (com filtros) |
| `POST` | `/api/orders/` | Criar ordem de compra |
| `POST` | `/api/orders/{id}/approve` | Aprovar ordem |
| `POST` | `/api/orders/{id}/reject` | Rejeitar ordem |

### Fornecedores (`/api/suppliers`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/suppliers/` | Listar fornecedores |
| `GET` | `/api/suppliers/{id}` | Detalhes do fornecedor |
| `GET` | `/api/suppliers/{id}/offers` | Ofertas do fornecedor |
| `POST` | `/api/suppliers/` | Criar fornecedor |
| `PUT` | `/api/suppliers/{id}` | Atualizar fornecedor |
| `DELETE` | `/api/suppliers/{id}` | Remover fornecedor |

### Chat com IA (`/api/chat`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/chat/sessions` | Listar sessões de chat |
| `POST` | `/api/chat/sessions` | Criar sessão |
| `DELETE` | `/api/chat/sessions/{id}` | Deletar sessão |
| `GET` | `/api/chat/sessions/{id}/messages` | Mensagens da sessão |
| `POST` | `/api/chat/sessions/{id}/messages` | Enviar mensagem ao agente |
| `WS` | `/api/chat/ws/{session_id}` | WebSocket para chat em tempo real |

### Agentes (`/api/agents`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/agents/` | Listar agentes do sistema |
| `POST` | `/api/agents/{id}/{action}` | Ativar/pausar/executar agente |

### Auditoria (`/api/audit`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/audit/decisions/` | Listar decisões auditadas |
| `GET` | `/api/audit/decisions/{id}` | Detalhes de uma decisão |
| `GET` | `/api/audit/stats/` | Estatísticas de auditoria |

### Machine Learning (`/ml`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/ml/train/all/async` | Treinar todos os modelos (async) |
| `POST` | `/ml/train/{sku}/async` | Treinar modelo por SKU (async) |
| `GET` | `/ml/predict/{sku}` | Previsão de preço por SKU |
| `GET` | `/ml/models` | Listar modelos treinados |
| `GET` | `/ml/models/{sku}` | Detalhes do modelo por SKU |

### RAG & Admin (`/api/rag`, `/admin`)
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/rag/status` | Status da sincronização RAG |
| `POST` | `/api/rag/sync` | Sincronizar catálogo → ChromaDB |
| `POST` | `/admin/cache/clear` | Limpar cache Redis |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Métricas Prometheus |

---

## 🛠 Stack Técnica

### Backend
| Tecnologia | Versão | Uso |
|------------|--------|-----|
| Python | 3.11 | Linguagem principal |
| FastAPI | latest | Framework web assíncrono |
| SQLModel | latest | ORM (SQLAlchemy + Pydantic) |
| SQLAlchemy | 2.0+ | Engine de banco de dados (sync + async) |
| Celery | 5.6+ | Task queue distribuída |
| Agno SDK | latest | Framework de agentes de IA multi-agente |
| Google Gemini | 2.5 Flash | LLM principal (com fallback chain: Flash → Lite → Pro) |
| ChromaDB | latest | Vector store para RAG |
| LangChain | latest | Pipeline RAG (embeddings + retrieval + chain) |
| StatsForecast | latest | Forecasting de séries temporais (AutoARIMA) |
| scikit-learn | latest | Feature engineering e métricas ML |
| Redis | 7 | Cache, pub/sub, Celery result backend |
| RabbitMQ | 3.13 | Message broker (Celery) com DLQ |
| MySQL | 8.0 | Banco de dados relacional |

### Frontend
| Tecnologia | Versão | Uso |
|------------|--------|-----|
| React | 18.3 | UI framework |
| TypeScript | 5.8 | Tipagem estática |
| Vite | 7.1 | Build tool & dev server (SWC) |
| Tailwind CSS | 3.4 | Framework CSS utility-first |
| shadcn/ui | latest | Componentes UI (Radix UI primitives) |
| TanStack Query | 5.83 | Gerenciamento de estado servidor |
| Axios | 1.12 | Cliente HTTP com interceptors |
| Recharts | 3.2 | Gráficos de preços e previsões |
| React Router | 6.30 | Roteamento SPA com lazy loading |
| react-markdown | 9.0 | Renderização de markdown no chat |

### Infraestrutura
| Tecnologia | Uso |
|------------|-----|
| Docker Compose | Orquestração de 10 serviços |
| Nginx | Reverse proxy + serving de assets estáticos |
| Prometheus | Coleta de métricas (API, LLM, HTTP) |
| Grafana | Dashboards de monitoramento |
| Flower | Monitoramento visual do Celery |

---

## 📐 Estrutura do Projeto

```
AutomacaoPMI/
├── app/                          # Backend Python
│   ├── main.py                   # FastAPI factory + middleware + routers
│   ├── agents/                   # Agentes de IA
│   │   ├── conversational_agent.py   # Agente conversacional principal
│   │   ├── supply_chain_team.py      # Time de analistas (4 agentes)
│   │   ├── tools_secure.py           # Ferramentas tenant-aware (633 linhas)
│   │   ├── knowledge.py              # RAG Agno (ChromaDB Knowledge)
│   │   ├── gemini_fallback.py        # Fallback chain (Flash → Lite → Pro)
│   │   ├── llm_config.py             # Configuração centralizada de LLM
│   │   ├── llm_metrics.py            # Métricas Prometheus para LLM
│   │   ├── models.py                 # Schemas Pydantic dos agentes
│   │   └── prompts/                  # Prompts YAML externalizados
│   ├── core/                     # Infraestrutura
│   │   ├── config.py                 # Settings (Pydantic BaseSettings)
│   │   ├── database.py               # Engines sync + async (pymysql + aiomysql)
│   │   ├── security.py               # JWT, bcrypt/argon2, auth dependencies
│   │   ├── celery_app.py             # Celery config (queues, beat, DLQ)
│   │   └── redis_client.py           # Redis singleton
│   ├── models/                   # Modelos de banco (20 tabelas)
│   │   ├── models.py                 # Modelos principais (252 linhas)
│   │   └── integration_models.py     # Modelos de integração
│   ├── routers/                  # 15 routers (52 endpoints)
│   ├── services/                 # 12 serviços de negócio
│   ├── ml/                       # Pipeline de Machine Learning
│   │   ├── training.py               # Treinamento StatsForecast
│   │   ├── prediction.py             # Previsão de preços
│   │   └── model_manager.py          # Gerenciamento de modelos
│   └── tasks/                    # Tarefas Celery
│       ├── agent_tasks.py            # Execução de análise via agentes
│       └── ml_tasks.py               # Treinamento ML assíncrono
├── FrontEnd/                     # Frontend React
│   ├── src/
│   │   ├── pages/                    # 10 páginas
│   │   ├── hooks/                    # 16 hooks customizados
│   │   ├── components/               # 12 business + 51 shadcn/ui
│   │   ├── services/api.ts           # Cliente HTTP Axios
│   │   └── types/api.types.ts        # Tipos TypeScript
│   ├── nginx.conf                    # Proxy reverso produção
│   └── Dockerfile                    # Build multi-stage (node → nginx)
├── scripts/                      # 14 scripts operacionais
│   ├── seed_full.py                  # Seeder completo (10 etapas)
│   └── train_all_phases.py           # Treinamento multi-fase
├── tests/                        # 14 arquivos de teste E2E (180 testes)
├── config/                       # Prometheus + Grafana configs
├── data/products_seed.csv        # 50 produtos (estofaria/ferragens)
├── docker-compose.yml            # 10 serviços Docker
├── requirements.txt              # Dependências Python
└── pyproject.toml                # Config (Ruff, MyPy, Pytest)
```

---

## 📊 Métricas do Projeto

| Métrica | Backend | Frontend | Total |
|---------|---------|----------|-------|
| **Linhas de código** | 17.005 | 9.987 | **~27.000** |
| **Arquivos fonte** | ~65 | 93 | **~158** |
| **Endpoints da API** | 52 | — | **52** |
| **Tabelas no banco** | 20 | — | **20** |
| **Páginas** | — | 10 | **10** |
| **Componentes** | — | 63 | **63** |
| **Hooks** | — | 16 | **16** |
| **Serviços** | 12 | 1 | **13** |
| **Agentes de IA** | 6 | — | **6** |
| **Tarefas Celery** | 4 | — | **4** |
| **Testes** | 180 | 4 | **184** |
| **Dependências** | 48 | 53 | **101** |
| **Serviços Docker** | — | — | **10** |

---

## 🧪 Testes

O projeto possui **180 testes E2E** cobrindo todas as camadas:

| Área | Arquivo | Cobertura |
|------|---------|-----------|
| Health | `test_e2e_health.py` | Endpoints de saúde e readiness |
| Autenticação | `test_e2e_auth.py` | Registro, login, JWT, validação de senha |
| Produtos | `test_e2e_products.py` | CRUD, busca, histórico de preços |
| Ordens | `test_e2e_orders.py` | CRUD, aprovação/rejeição, filtros |
| Fornecedores | `test_e2e_suppliers.py` | CRUD, ofertas |
| Dashboard | `test_e2e_dashboard.py` | KPIs, alertas |
| Chat | `test_e2e_chat.py` | Sessões, mensagens |
| Agentes | `test_e2e_agents.py` | CRUD, ativação |
| Auditoria | `test_e2e_audit.py` | Decisões, estatísticas |
| ML | `test_e2e_ml.py` | Modelos treinados |
| RAG | `test_e2e_rag.py` | Status do vector store |
| Segurança | `test_e2e_security.py` | RBAC, acesso não-autenticado, restrições |
| Serviços | `test_e2e_services.py` | Testes unitários da camada de serviços |
| Multi-Tenant | `test_e2e_tenant.py` | Isolamento de dados entre tenants |

**Banco de testes**: SQLite in-memory (substitui MySQL)  
**Framework**: pytest + pytest-asyncio + FastAPI TestClient

---

## 🔒 Segurança

- **Autenticação JWT** com bcrypt/argon2 password hashing (passlib)
- **Multi-tenancy row-level** — queries filtradas por `tenant_id` em todas as operações
- **CORS configurado** para origens específicas (dev: 5173, 3000, 8080)
- **Portas internas protegidas** — MySQL, Redis, RabbitMQ não expostos externamente
- **Credenciais criptografadas** — modelo `IntegrationCredential` com Fernet encryption
- **Fallback chain LLM** — exponential backoff entre modelos Gemini
- **Dead Letter Queues** — mensagens falhas isoladas por fila Celery
- **Auditoria completa** — todas as decisões de agentes registradas com raciocínio

---

## 📄 Licença

Projeto proprietário. Todos os direitos reservados.

---

## 👤 Autor

Desenvolvido como plataforma SaaS de automação de compras industriais com inteligência artificial.

