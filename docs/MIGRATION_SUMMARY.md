# Resumo da Migração: LangChain/LangGraph → Agno

## 📋 Visão Geral

Migração completa do sistema de agentes de **LangChain/LangGraph** para **Agno**, mantendo compatibilidade total com **OpenRouter** para acesso aos modelos de linguagem.

---

## ✅ Arquivos Modificados

### 1. **requirements.txt**
**Mudanças:**
- ❌ Removido: `langchain`, `langgraph`, `langchain-community`, `langchain-openai`, `langchain-experimental`, `langchain-chroma`
- ✅ Adicionado: `agno==0.0.36`, `openai==1.59.5`

### 2. **app/agents/tools.py**
**Mudanças:**
- Convertido de ferramentas LangChain (`StructuredTool`) para `Toolkit` do Agno
- Criada classe `SupplyChainToolkit` que herda de `agno.tools.Toolkit`
- Ferramentas implementadas como métodos da classe:
  - `lookup_product()` - Consulta produto por SKU
  - `load_demand_forecast()` - Carrega previsão de demanda
  - `scrape_latest_price()` - Scraping de preços do Mercado Livre
  - `compute_distance()` - Cálculo de distâncias geográficas
  - `wikipedia_search()` - Busca na Wikipedia
  - `tavily_search()` - Busca web (se API key configurada)
- Mantidas funções auxiliares para compatibilidade retroativa

### 3. **app/agents/supply_chain_team.py** ⭐ (NOVO)
**Funcionalidade:**
- Substitui completamente o `supply_chain_graph.py` do LangGraph
- Implementa fluxo sequencial de 4 agentes especialistas usando `agno.team.Team`:
  1. **AnalistaDemanda** - Análise de necessidade de reposição
  2. **PesquisadorMercado** - Coleta de preços e fornecedores
  3. **AnalistaLogistica** - Avaliação de custos logísticos
  4. **GerenteCompras** - Decisão final de compra
- Configuração do modelo via `_get_openai_model()` apontando para OpenRouter
- Função `execute_supply_chain_team()` para execução completa do pipeline

### 4. **app/agents/conversational_agent.py**
**Mudanças:**
- Substituído `ChatOpenAI` do LangChain por `agno.models.openai.OpenAI`
- Refatorada função `_get_llm()` → `_get_openai_model()`
- `extract_entities_with_llm()` agora usa `Agent` do Agno em vez de chains do LangChain
- Mantida toda a lógica de NLU, contexto de sessão e RAG

### 5. **app/services/rag_service.py**
**Mudanças:**
- Removida dependência de `langchain_chroma` e `langchain_openai`
- Migrado para uso direto do `chromadb` (cliente nativo)
- Implementada função `_get_embedding()` usando cliente `openai.OpenAI` com OpenRouter
- Refatoradas todas as funções para usar API nativa do ChromaDB:
  - `index_chat_message()` - Indexa mensagens do chat
  - `index_product_catalog()` - Indexa catálogo de produtos
  - `semantic_search_messages()` - Busca semântica em mensagens
  - `get_relevant_context()` - Obtém contexto RAG

### 6. **app/services/agent_service.py**
**Mudanças:**
- Substituído import de `build_supply_chain_graph` por `execute_supply_chain_team`
- Removida lógica de compilação de grafo (`_get_compiled_graph`)
- Simplificada função `execute_supply_chain_analysis()` para chamar diretamente o team do Agno
- Mantida toda a lógica de gerenciamento de agentes no banco de dados

### 7. **app/agents/__init__.py**
**Mudanças:**
- Atualizado para exportar classes e funções do Agno
- Exports: `SupplyChainToolkit`, `create_supply_chain_team`, `execute_supply_chain_team`

---

## 🔧 Configuração OpenRouter

A configuração do OpenRouter permanece a mesma via variáveis de ambiente:

```bash
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL_NAME=mistralai/mistral-small-3.1-24b-instruct:free
```

O Agno usa internamente o cliente da OpenAI, que é compatível com endpoints OpenRouter.

---

## 📦 Instalação de Dependências

Execute os seguintes comandos para instalar as novas dependências:

```bash
pip install -r requirements.txt
```

Ou via Docker (recomendado):

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

---

## 🧪 Testes Recomendados

### 1. Teste de Análise de Produto
```bash
# Via API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Analisar compra do SKU_001", "session_id": 1}'
```

### 2. Teste do Team de Agentes
```python
from app.agents.supply_chain_team import execute_supply_chain_team

result = execute_supply_chain_team(sku="SKU_001")
print(result["recommendation"])
```

### 3. Teste de Extração de Entidades
```python
from app.agents.conversational_agent import extract_entities
from app.core.database import get_session

with get_session() as session:
    entities = extract_entities("Preciso comprar 50 unidades do SKU_001", session, session_id=1)
    print(entities)
```

---

## 🚨 Possíveis Problemas e Soluções

### Problema 1: Erro ao importar Agno
**Solução:** Certifique-se de que instalou `agno==0.0.36`
```bash
pip install agno==0.0.36
```

### Problema 2: ChromaDB retornando erros
**Solução:** Limpe o diretório de persistência do ChromaDB e reindexe
```bash
rm -rf data/chroma
# Reinicie a aplicação para recriar as collections
```

### Problema 3: OpenRouter não responde
**Solução:** Verifique se as variáveis de ambiente estão configuradas
```bash
echo $OPENROUTER_API_KEY
# Se vazio, configure no arquivo .env
```

### Problema 4: JSON parsing errors nos agentes
**Solução:** Os agentes Agno podem retornar markdown. O código já trata isso extraindo blocos ```json```. Se persistir, ajuste a temperatura do modelo para valores mais baixos (0.1-0.2).

---

## 📊 Benefícios da Migração

1. **Performance** 
   - Menor overhead de abstrações
   - Execução mais rápida de agentes

2. **Simplicidade**
   - API mais intuitiva e "Pythonica"
   - Menos código boilerplate

3. **Manutenibilidade**
   - Código mais limpo e legível
   - Debugging mais fácil

4. **Compatibilidade**
   - 100% compatível com OpenRouter
   - Suporte a múltiplos provedores de LLM

---

## 🗑️ Arquivos que Podem Ser Removidos

Após validar que tudo funciona corretamente, você pode remover:

```bash
rm app/agents/supply_chain_graph.py
```

**Atenção:** Faça backup antes de remover!

---

## 📝 Próximos Passos

1. ✅ Instalar dependências: `pip install -r requirements.txt`
2. ✅ Verificar variáveis de ambiente (.env)
3. ✅ Executar testes unitários
4. ✅ Testar fluxo completo de análise de compra
5. ✅ Monitorar logs para erros
6. ✅ Validar respostas dos agentes
7. ✅ Remover `supply_chain_graph.py` (opcional)

---

## 🆘 Suporte

Se encontrar problemas:
- Consulte a documentação oficial: https://docs.agno.com/
- Verifique os logs: `docker-compose logs -f api`
- Revise este documento de migração

---

**Data da Migração:** 2025-10-09  
**Framework Anterior:** LangChain 0.x + LangGraph  
**Framework Atual:** Agno 0.0.36  
**Status:** ✅ Migração Completa
