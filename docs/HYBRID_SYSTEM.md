# Sistema Híbrido RAG + SQL 🚀

## 🎯 Objetivo

Responder **QUALQUER** pergunta sobre produtos combinando:
- **RAG (Busca Semântica)**: Para perguntas sobre descrições, características, comparações
- **SQL (Consultas Estruturadas)**: Para filtros, agregações, comparações numéricas
- **Híbrido**: Combina ambos para respostas completas

---

## 🏗️ Arquitetura

```
Pergunta do Usuário
       ↓
┌──────────────────────────────────┐
│  Hybrid Query Service            │
│  - Analisa intent com LLM        │
│  - Decide: SQL, RAG ou Híbrido   │
└──────────────────────────────────┘
       ↓
   ┌───┴───┐
   ↓       ↓
┌─────┐ ┌─────┐
│ SQL │ │ RAG │
└─────┘ └─────┘
   ↓       ↓
   └───┬───┘
       ↓
  Resposta Final
  (Combinada pelo LLM)
```

---

## 📊 Tipos de Consultas

### 1. **Consultas SQL** (Estruturadas)
Quando usar: Filtros, agregações, comparações numéricas

**Exemplos:**
- ✅ "Quais produtos com estoque baixo?"
- ✅ "Quantos produtos temos?"
- ✅ "Produtos com estoque maior que 100"
- ✅ "Produtos da categoria X"

**O que faz:**
- Consulta direta ao banco MySQL
- Filtros WHERE, ORDER BY, GROUP BY
- Retorna dados estruturados

### 2. **Consultas RAG** (Semânticas)
Quando usar: Descrições, características, informações textuais

**Exemplos:**
- ✅ "Me fale sobre o produto SKU_123"
- ✅ "Qual a diferença entre produto A e B?"
- ✅ "Produtos similares a parafusos"
- ✅ "Características do produto X"

**O que faz:**
- Busca semântica no ChromaDB
- Embeddings Google AI (text-embedding-004)
- Retorna contexto relevante

### 3. **Consultas Híbridas** (SQL + RAG)
Quando usar: Perguntas complexas que precisam de ambos

**Exemplos:**
- ✅ "Quais produtos com estoque baixo e suas características?"
- ✅ "Me mostre produtos da categoria X com descrição"
- ✅ "Produtos críticos e por que são importantes"

**O que faz:**
1. SQL busca dados estruturados
2. RAG enriquece com contexto semântico
3. LLM combina tudo em resposta natural

---

## 🔧 Componentes

### 1. `sql_query_tool.py`
Ferramentas SQL para consultas estruturadas:
- `query_products_with_filters()`: Filtros customizados
- `get_stock_statistics()`: Estatísticas agregadas
- `search_products_by_name_or_sku()`: Busca textual
- `get_products_sorted_by_stock()`: Ordenação

### 2. `rag_service.py`
Busca semântica com LangChain + Google AI:
- `index_product_catalog()`: Indexa produtos no ChromaDB
- `query_product_catalog_with_google_rag()`: Consulta RAG
- Embeddings: Google text-embedding-004
- LLM: Gemini 2.5 Flash

### 3. `hybrid_query_service.py`
Orquestrador inteligente:
- `analyze_query_intent()`: LLM analisa a pergunta
- `execute_hybrid_query()`: Executa SQL e/ou RAG
- `format_final_response()`: Combina resultados

### 4. `chat_service.py`
Interface do chat:
- `handle_natural_conversation()`: Usa sistema híbrido
- Integração transparente para o usuário

---

## 🎬 Fluxo de Execução

### Exemplo: "Quais meus produtos com estoque baixos?"

1. **Análise de Intent** (LLM)
   ```json
   {
     "query_type": "sql",
     "needs_stock_filter": true,
     "stock_filter_type": "low",
     "reasoning": "Pergunta requer filtro WHERE estoque_atual <= estoque_minimo"
   }
   ```

2. **Execução SQL**
   ```python
   query_products_with_filters(
       db_session,
       estoque_baixo=True,
       limit=50
   )
   ```
   Retorna: Lista de produtos com estoque <= mínimo

3. **Formatação**
   ```markdown
   ⚠️ **Encontrei 15 produto(s) com estoque baixo:**
   
   • **Parafuso M8 Inox** (SKU: SKU_001)
     - Estoque atual: 5 unidades
     - Estoque mínimo: 10 unidades
     - Faltam: 5 unidades
   
   • **Rolamento SKF 6205** (SKU: SKU_002)
     ...
   ```

---

## 🚀 Como Usar

### No Chat
Simplesmente pergunte naturalmente:

```
Usuário: "Quais produtos com estoque baixo?"
Bot: [Lista formatada com produtos]

Usuário: "Me fale sobre o SKU_001"
Bot: [Descrição detalhada do produto]

Usuário: "Produtos críticos da categoria eletrônicos"
Bot: [Combina filtro SQL + contexto RAG]
```

### Programaticamente
```python
from app.services.hybrid_query_service import execute_hybrid_query

response = execute_hybrid_query(
    "Quais produtos com estoque baixo?",
    db_session
)
print(response)
```

---

## 🎯 Vantagens

1. **Flexibilidade Total**: Responde qualquer tipo de pergunta
2. **Precisão**: SQL para dados exatos, RAG para contexto
3. **Inteligente**: LLM decide automaticamente qual ferramenta usar
4. **Natural**: Usuário não precisa saber SQL ou embeddings
5. **Escalável**: Adicionar novas ferramentas é fácil

---

## 📝 Próximos Passos

- [ ] Cache de consultas frequentes
- [ ] Suporte a filtros mais complexos (ranges, múltiplas categorias)
- [ ] Histórico de conversas para contexto
- [ ] Sugestões de perguntas relacionadas
- [ ] Exportação de resultados (CSV, PDF)

---

## 🔍 Debug

Para ver o que está acontecendo, observe os logs:

```bash
docker-compose logs api -f | grep -E "(Intent|SQL|RAG|Híbrido)"
```

Você verá:
- `🧠 Intent detectado: sql` - Tipo de consulta escolhido
- `📊 SQL retornou 15 produtos` - Resultados SQL
- `🤖 RAG respondeu: ...` - Resposta RAG
- `💬 Sistema Híbrido processando` - Início do processo
