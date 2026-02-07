# 🏭 Automação Inteligente de Ordens de Compra

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**Sistema de IA Multi-Agente para Automação de Compras Industriais**

[Funcionalidades](#-funcionalidades) •
[Arquitetura](#-arquitetura) •
[Instalação](#-instalação-rápida) •
[Uso](#-como-usar) •
[Documentação](#-documentação)

</div>

---

## 📋 Sobre o Projeto

Sistema completo de **Inteligência Artificial** para automatizar e otimizar decisões de compra em **Pequenas e Médias Indústrias (PMI)**. Utiliza uma arquitetura multi-agente com IA generativa (Google Gemini 2.5), Machine Learning para previsões e RAG (Retrieval-Augmented Generation) para consultas inteligentes.

### 🎯 Problema Resolvido

- ❌ Decisões de compra manuais e demoradas
- ❌ Falta de análise de múltiplos fornecedores
- ❌ Ausência de previsões de demanda
- ❌ Processos não documentados

### ✅ Solução

- ✅ **Chat inteligente** para consultas em linguagem natural
- ✅ **Análise automatizada** por time de agentes IA
- ✅ **Previsões de demanda** com Machine Learning
- ✅ **Recomendações justificadas** com rastreabilidade

---

## ✨ Funcionalidades

| Módulo | Descrição |
|--------|-----------|
| 🤖 **Chat IA** | Converse naturalmente para obter recomendações de compra |
| 📊 **Dashboard** | Visualize métricas, previsões e alertas em tempo real |
| 📦 **Catálogo** | Gerencie produtos com estoque, preços e fornecedores |
| 📋 **Ordens** | Crie, aprove ou rejeite ordens de compra automaticamente |
| 🚚 **Fornecedores** | Gestão completa de fornecedores e ofertas |
| 📝 **Auditoria** | Visualize histórico de decisões dos agentes |
| 💬 **Histórico Chat** | Navegue entre conversas anteriores |
| 🔮 **Previsões ML** | Previsão de demanda com AutoARIMA (StatsForecast) |
| 🔍 **RAG** | Busca semântica inteligente no catálogo de produtos |
| 🔄 **Fallback AI** | Alternância automática entre modelos Gemini |
| 🔐 **Autenticação** | Login seguro com JWT |

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                     │
│          TypeScript • TailwindCSS • shadcn/ui • Recharts        │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
├──────────────┬──────────────┬────────────────┬──────────────────┤
│   Routers    │   Services   │    Agents      │       ML         │
│  (Endpoints) │   (Lógica)   │  (Multi-Agent) │   (Previsões)    │
└──────────────┴──────────────┴────────────────┴──────────────────┘
        ↓               ↓              ↓               ↓
┌───────────┐   ┌────────────┐   ┌──────────┐   ┌─────────────────┐
│  MySQL    │   │  ChromaDB  │   │  Gemini  │   │   StatsForecast │
│   8.0     │   │  (Vetores) │   │   2.5    │   │   (AutoARIMA)   │
└───────────┘   └────────────┘   └──────────┘   └─────────────────┘
```

### 🤖 Sistema Multi-Agente

```
                    ┌─────────────────────────────────┐
                    │   AGENTE CONVERSACIONAL         │
                    │        (Gerente)                │
                    │   Interface com usuário         │
                    └───────────────┬─────────────────┘
                                    │ Delega
        ┌───────────────┬───────────┴───────────┬───────────────┐
        ↓               ↓                       ↓               ↓
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Analista    │ │  Pesquisador  │ │   Analista    │ │   Gerente     │
│   de Demanda  │ │   de Mercado  │ │   Logística   │ │   de Compras  │
├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤
│ • Estoque     │ │ • Ofertas     │ │ • Fornecedor  │ │ • Consolida   │
│ • Previsão    │ │ • Tendências  │ │ • Custo total │ │ • Decisão     │
│   demanda     │ │   de mercado  │ │   aquisição   │ │   final       │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

---

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.11+** - Linguagem principal
- **FastAPI** - Framework web assíncrono
- **SQLModel** - ORM moderno (SQLAlchemy + Pydantic)
- **Agno 2.1.3+** - Framework de agentes IA
- **LangChain** - Orquestração para RAG
- **Celery + Redis** - Processamento assíncrono

### Frontend
- **React 18.3** - Biblioteca UI
- **TypeScript 5.8** - Tipagem estática
- **Vite 7.1** - Build tool
- **TailwindCSS 3.4** - Estilização
- **shadcn/ui** - Componentes UI
- **Recharts** - Gráficos

### IA/ML
- **Google Gemini 2.5 Flash** - LLM principal
- **ChromaDB** - Vector database
- **StatsForecast (AutoARIMA)** - Previsões
- **Google AI Embeddings** - gemini-embedding-001

### Infraestrutura
- **Docker & Docker Compose** - Containerização
- **MySQL 8.0** - Banco de dados
- **Redis 7** - Message broker
- **Nginx** - Servidor web (frontend)

---

## 🚀 Instalação Rápida

### Pré-requisitos

- Docker & Docker Compose
- Chave API do Google (Gemini)

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/automatizador-ordens-compra.git
cd automatizador-ordens-compra
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env`:

```env
# Obrigatório - Google AI
GOOGLE_API_KEY=sua_chave_google_api

# Banco de dados
MYSQL_ROOT_PASSWORD=root_password
MYSQL_DATABASE=app_db
MYSQL_USER=app_user
MYSQL_PASSWORD=app_password

# Opcional - Tavily (Web Search)
TAVILY_API_KEY=sua_chave_tavily
```

> 📌 Obtenha sua chave Google em: https://aistudio.google.com/app/apikey

### 3. Inicie os containers

```bash
docker compose up -d
```

### 4. Acesse a aplicação

| Serviço | URL |
|---------|-----|
| 🌐 **Frontend** | http://localhost:3000 |
| ⚡ **API** | http://localhost:8000 |
| 📚 **Docs (Swagger)** | http://localhost:8000/docs |

---

## 📖 Como Usar

### 1. Criar uma conta

Acesse http://localhost:3000/register e crie sua conta.

### 2. Popular o banco de dados

```bash
# Produtos de exemplo
docker compose exec api python scripts/seed_database.py

# Sincronizar RAG
docker compose exec api python scripts/sync_vectors.py
```

### 3. Conversar com o Agente

Acesse a página **Agents** e faça perguntas como:

#### Perguntas Simples (Resposta Direta)
```
"Qual o estoque do SKU_001?"
"Me mostre produtos da categoria ferramentas"
"Previsão de preço para SKU_001 nos próximos 7 dias?"
```

#### Perguntas Complexas (Análise pelo Time)
```
"Devo comprar o produto SKU_001?"
"Qual fornecedor é melhor para parafusos?"
"Analise a necessidade de reposição para SKU_001"
```

### 4. Exemplo de Resposta

```markdown
✅ **Recomendo APROVAR a compra de 100 unidades**

**Fornecedor Recomendado:** Distribuidora Nacional
- 💰 Preço: R$ 1.450,00 (R$ 14,50/un)
- ⏱️ Prazo: 5 dias úteis  
- ⭐ Confiabilidade: 95%

**Justificativa:**
- Estoque atual (45 un) abaixo do mínimo (80 un)
- Previsão ML indica tendência de alta (+3%)
- Melhor custo-benefício entre 5 fornecedores

**Próximos passos:**
1. Emitir ordem de compra
2. Agendar entrega para +5 dias
```

---

## 📂 Estrutura do Projeto

```
📦 projeto/
├── 📂 app/                    # Backend FastAPI
│   ├── 📂 agents/             # Sistema Multi-Agente
│   ├── 📂 core/               # Configurações (DB, Auth)
│   ├── 📂 ml/                 # Machine Learning
│   ├── 📂 models/             # Modelos SQLModel
│   ├── 📂 routers/            # API Endpoints
│   ├── 📂 services/           # Lógica de negócio
│   └── main.py                # Entry point
├── 📂 FrontEnd/               # React + Vite
│   ├── 📂 src/
│   │   ├── 📂 components/     # Componentes React
│   │   ├── 📂 pages/          # Páginas
│   │   └── App.tsx            # Entry point
│   └── package.json
├── 📂 scripts/                # Scripts utilitários
├── 📂 migrations/             # Migrations SQL
├── docker-compose.yml         # Orquestração Docker
├── Dockerfile                 # Build API
├── requirements.txt           # Dependências Python
└── README.md                  # Este arquivo
```

---

## 🔧 Comandos Úteis

### Docker

```bash
# Iniciar
docker compose up -d

# Ver logs
docker compose logs -f api

# Parar
docker compose down

# Reconstruir
docker compose build --no-cache
```

### Scripts

```bash
# Popular banco
docker compose exec api python scripts/seed_database.py

# Sincronizar RAG
docker compose exec api python scripts/sync_vectors.py

# Gerar dados sintéticos
docker compose exec api python scripts/generate_realistic_data.py

# Treinar modelos ML
docker compose exec api python scripts/train_all_phases.py
```

### Desenvolvimento Local

```bash
# Backend
cd projeto
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd FrontEnd
npm install
npm run dev
```

---

## 📡 API Endpoints

### Autenticação

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/auth/login` | Login (retorna JWT) |
| POST | `/auth/register` | Criar conta |
| GET | `/auth/me` | Usuário atual |

### Chat

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/chat/sessions` | Listar sessões |
| POST | `/api/chat/sessions` | Nova sessão |
| DELETE | `/api/chat/sessions/{id}` | Apagar sessão |
| POST | `/api/chat/sessions/{id}/messages` | Enviar mensagem |
| GET | `/api/chat/sessions/{id}/history` | Histórico |

### Fornecedores

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/suppliers/` | Listar fornecedores |
| GET | `/api/suppliers/{id}` | Detalhes |
| GET | `/api/suppliers/{id}/offers` | Ofertas do fornecedor |
| POST | `/api/suppliers/` | Criar fornecedor |
| PUT | `/api/suppliers/{id}` | Atualizar |
| DELETE | `/api/suppliers/{id}` | Remover |

### Auditoria

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/audit/decisions/` | Listar decisões |
| GET | `/api/audit/decisions/{id}` | Detalhes da decisão |
| GET | `/api/audit/stats/` | Estatísticas |

### Produtos

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/products/` | Listar produtos |
| GET | `/api/products/{id}` | Detalhes |
| POST | `/api/products/` | Criar produto |

### Ordens

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/orders/` | Listar ordens |
| POST | `/api/orders/` | Criar ordem |
| POST | `/api/orders/{id}/approve` | Aprovar |
| POST | `/api/orders/{id}/reject` | Rejeitar |

### Machine Learning

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/ml/forecast/{sku}` | Previsão para SKU |
| GET | `/ml/metrics` | Métricas do modelo |

---

## 🔐 Variáveis de Ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `GOOGLE_API_KEY` | ✅ | Chave API Google Gemini |
| `DATABASE_URL` | ✅ | URL conexão MySQL |
| `MYSQL_*` | ✅ | Credenciais MySQL |
| `SECRET_KEY` | ⚠️ | Chave JWT (gerar segura) |
| `TAVILY_API_KEY` | ❌ | Web search (opcional) |
| `REDIS_URL` | ❌ | URL Redis (padrão: broker:6379) |

---

## 🐛 Troubleshooting

### Erro: "GOOGLE_API_KEY não encontrada"
```bash
# Verificar .env
cat .env | grep GOOGLE_API_KEY

# Recriar containers
docker compose down && docker compose up -d
```

### Erro: "Conexão com banco recusada"
```bash
# Aguardar MySQL iniciar (pode levar ~30s)
docker compose logs -f db

# Verificar status
docker compose ps
```

### Erro: "ChromaDB instance conflict"
```bash
# Limpar e resincronizar
rm -rf data/chroma
docker compose exec api python scripts/sync_vectors.py
```

### Frontend não conecta na API
```bash
# Verificar URL no frontend
cat FrontEnd/.env.local
# Deve conter: VITE_API_URL=http://localhost:8000
```

---

## 📚 Documentação

Para documentação técnica detalhada, consulte:

- 📖 [**DOCUMENTACAO_COMPLETA.md**](./DOCUMENTACAO_COMPLETA.md) - Documentação técnica completa

---

## 🗺️ Roadmap

- [x] Sistema Multi-Agente com Agno
- [x] RAG com ChromaDB + LangChain
- [x] Previsões com StatsForecast
- [x] Frontend React completo
- [x] Autenticação JWT
- [x] Página de Fornecedores
- [x] Log de Auditoria
- [x] Histórico de Chat
- [x] Fallback automático de modelos Gemini
- [ ] Integração com ERPs
- [ ] App mobile
- [ ] Monitoramento Prometheus/Grafana
- [ ] Deploy em cloud (AWS/GCP)

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

