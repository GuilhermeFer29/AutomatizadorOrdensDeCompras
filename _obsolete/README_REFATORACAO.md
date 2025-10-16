# 📦 Pasta _obsolete - Código Legado Arquivado

**Data da Refatoração**: 2025-10-16  
**Responsável**: Auditoria Arquitetural Completa

## 🎯 Objetivo desta Pasta

Esta pasta contém todo o código identificado como **obsoleto, descontinuado ou não utilizado** durante a auditoria completa do projeto. Os arquivos foram **movidos (não deletados)** para permitir revisão e possível recuperação antes da exclusão permanente.

---

## 📋 Arquivos Movidos

### 1️⃣ **Funcionalidade de Scraping (Descontinuada)**

#### `app/tasks/scraping_tasks.py`
- **Motivo**: Funcionalidade de scraping do Mercado Livre foi descontinuada
- **Referência**: Documentado em `docs/SCRAPER_DESATIVADO.md`
- **Dependências removidas**: `beautifulsoup4`
- **Impacto**: Endpoint `/tasks/scrape/all` removido do `tasks_router.py`

#### `scripts/run_bulk_scraping.py`
- **Motivo**: Script de scraping em lote obsoleto
- **Dependências**: `app.services.scraping_service` (já não existe)

---

### 2️⃣ **Código Legado OpenRouter/DeepSeek**

#### `app/agents/supply_chain_graph.py`
- **Motivo**: Usa `ChatOpenAI` com API OpenRouter/DeepSeek (legado pré-Gemini)
- **Status**: NÃO migrado para Google Gemini
- **Substituído por**: Sistema híbrido Agno + LangChain RAG
- **APIs antigas**: `OPENROUTER_API_KEY`, `deepseek/deepseek-chat-v3-0324:free`

---

### 3️⃣ **Scripts de Migração de Uso Único**

#### `scripts/migrate_chat_messages_to_text.py`
- **Motivo**: Migração de schema do banco já executada
- **Função**: Alterava colunas `content` e `metadata_json` para TEXT
- **Status**: Migração concluída com sucesso

---

### 4️⃣ **Backup de Configuração**

#### `requirements.txt.old`
- **Motivo**: Backup antes da limpeza de dependências
- **Removido**: `beautifulsoup4`, `google-genai` (duplicado)
- **Mantido**: `langchain*` (arquitetura híbrida RAG ativa)

---

## 🔧 Refatorações Realizadas

### Arquivos Modificados

1. **`app/services/task_service.py`**
   - ❌ Removido: `import scraping_tasks`
   - ❌ Removido: `trigger_scrape_all_products_task()`

2. **`app/routers/tasks_router.py`**
   - ❌ Removido: Endpoint `POST /tasks/scrape/all`
   - ❌ Removido: Import `trigger_scrape_all_products_task`

3. **`app/agents/tools.py`**
   - ❌ Removido: `from app.services.scraping_service import ...`
   - ❌ Removido: `_format_outcome()` (função auxiliar do scraping)
   - ❌ Removido: `scrape_latest_price()` do `SupplyChainToolkit`
   - ❌ Removido: Import `asdict` (não utilizado)

4. **`requirements.txt`**
   - ❌ Removido: `beautifulsoup4` (scraping)
   - ❌ Removido: `google-genai` (duplicado, mantido `google-generativeai`)
   - ✅ Mantido: `requests` (usado por `cep_service.py` e `geolocation_service.py`)
   - ✅ Mantido: `langchain*` (arquitetura RAG híbrida ativa)

---

## ⚠️ Decisões Arquiteturais Importantes

### LangChain: Por que foi MANTIDO?

**NÃO é código legado!** O projeto usa uma **arquitetura híbrida intencional**:

```
┌─────────────────────────────────────────┐
│  Agno Agent (Orquestração Principal)   │
│         (Google Gemini 2.5 Flash)      │
└────────────┬────────────────────────────┘
             │
             ├─► ProductCatalogTool (ponte)
             │         │
             │         ▼
             │   ┌──────────────────────────┐
             │   │  LangChain RAG Service   │
             │   │  (Google Embeddings +    │
             │   │   Gemini 2.5 Flash)      │
             │   └──────────────────────────┘
             │
             └─► SupplyChainToolkit
```

**Arquivos ativos com LangChain**:
- `app/services/rag_service.py` ✅
- `app/services/hybrid_query_service.py` ✅
- `app/agents/conversational_agent.py` ✅

---

## 🚀 Próximos Passos

### Antes de Deletar Permanentemente

1. ✅ Testar aplicação completa (Fase 3)
2. ✅ Validar funcionalidades principais
3. ✅ Confirmar build Docker limpo
4. ⏳ **Aguardar aprovação final para exclusão**

### Se Necessário Recuperar

```bash
# Restaurar arquivo específico
cp _obsolete/app/tasks/scraping_tasks.py app/tasks/

# Restaurar requirements antigo
cp _obsolete/requirements.txt.old requirements.txt
```

---

## 📊 Impacto Estimado

| Métrica | Antes | Depois | Redução |
|---------|-------|--------|---------|
| **Arquivos em `app/tasks/`** | 5 | 4 | -20% |
| **Endpoints em `/tasks`** | 3 | 2 | -33% |
| **Dependências pip** | 33 | 31 | -6% |
| **Código legado** | ~500 linhas | 0 | -100% |
| **APIs LLM ativas** | 3 (Gemini, OpenRouter, DeepSeek) | 1 (Gemini) | -66% |

---

## 📝 Conclusão

A base de código está **significativamente mais limpa e manutenível**. Todos os componentes obsoletos foram arquivados de forma segura, mantendo a estrutura de diretórios original para facilitar a revisão.

**Status**: ✅ Pronto para o desenvolvimento do módulo de Machine Learning avançado

---

*Gerado automaticamente pela Auditoria Arquitetural - 2025-10-16*
