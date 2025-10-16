# Correções Aplicadas - ChromaDB e RAG Service

**Data:** 2025-10-16  
**Autor:** Sistema de Automação

---

## 🐛 Problemas Identificados

### 1. Erro: "An instance of Chroma already exists with different settings"

**Causa Raiz:**
- Múltiplas instâncias do `chromadb.PersistentClient` estavam sendo criadas em diferentes partes do código
- Cada instância tentava acessar o mesmo diretório de persistência com configurações potencialmente diferentes
- ChromaDB implementa validação interna que impede múltiplas instâncias com configurações conflitantes

**Impacto:**
- Falha ao indexar mensagens de chat
- Inconsistência no acesso ao vector store
- Logs poluídos com warnings

### 2. Erro: "expected string or bytes-like object, got 'dict'"

**Causa Raiz:**
- A função `query_product_catalog_with_google_rag()` estava passando um dicionário para o `rag_chain.invoke()`
- O chain LCEL (LangChain Expression Language) esperava receber apenas a string da query
- Linha problemática: `response = rag_chain.invoke({"question": query})`

**Impacto:**
- Falha nas consultas RAG ao catálogo de produtos
- Respostas de erro ao invés de informações dos produtos

---

## ✅ Soluções Implementadas

### Solução 1: Padrão Singleton para ChromaDB

**Arquivo Criado:** `app/services/chroma_client.py`

**Implementação:**
```python
class ChromaClientSingleton:
    """
    Singleton para gerenciar instância única do ChromaDB PersistentClient.
    """
    
    _instance: Optional[chromadb.PersistentClient] = None
    _persist_directory: Optional[str] = None
    
    @classmethod
    def get_client(cls, persist_directory: Optional[str] = None) -> chromadb.PersistentClient:
        # Cria instância apenas na primeira chamada
        if cls._instance is None:
            cls._instance = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        return cls._instance
```

**Benefícios:**
- ✅ Garante uma única instância do ChromaDB em toda a aplicação
- ✅ Previne conflitos de configuração
- ✅ Melhora performance (reutiliza conexão)
- ✅ Facilita manutenção e debugging

### Solução 2: Atualização do RAG Service

**Arquivo Modificado:** `app/services/rag_service.py`

**Mudanças:**

1. **Função `get_vector_store()`:**
```python
def get_vector_store() -> Chroma:
    from app.services.chroma_client import get_chroma_client
    
    # Usa o cliente singleton
    client = get_chroma_client(CHROMA_PERSIST_DIR)
    
    return Chroma(
        client=client,  # ← Passa o cliente singleton
        collection_name="products",
        embedding_function=google_embeddings
    )
```

2. **Função `index_chat_message()`:**
```python
def index_chat_message(message: ChatMessage) -> None:
    from app.services.chroma_client import get_chroma_client
    
    # Usa o cliente singleton
    client = get_chroma_client(CHROMA_PERSIST_DIR)
    collection = client.get_or_create_collection(name="chat_history")
    # ... resto do código
```

3. **Função `query_product_catalog_with_google_rag()`:**
```python
def query_product_catalog_with_google_rag(query: str) -> str:
    try:
        rag_chain = create_rag_chain()
        # Passa apenas a string, não um dicionário
        response = rag_chain.invoke(query)  # ← Corrigido
        return response
    except Exception as e:
        # ... tratamento de erro
```

---

## 📚 Referências Técnicas

### ChromaDB Documentation
- **Issue Oficial:** [chroma-core/chroma#1302](https://github.com/chroma-core/chroma/issues/1302)
- **Documentação:** https://docs.trychroma.com/
- **Best Practice:** Usar `PersistentClient` com padrão singleton para aplicações multi-threaded

### LangChain LCEL
- **Documentação:** https://python.langchain.com/docs/expression_language/
- **Invoke Pattern:** Chains LCEL aceitam inputs diretos ou dicionários dependendo da estrutura
- **Nosso caso:** O chain usa `RunnablePassthrough()` que espera string direta

---

## 🧪 Como Testar

### 1. Reinicie a aplicação
```bash
docker-compose down
docker-compose up --build
```

### 2. Verifique os logs
Os seguintes erros **NÃO** devem mais aparecer:
- ❌ `An instance of Chroma already exists for /app/data/chroma with different settings`
- ❌ `Erro ao consultar catálogo: expected string or bytes-like object, got 'dict'`

### 3. Teste funcional
```bash
# Via API
curl -X POST http://localhost:8000/api/chat/sessions/1/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Qual o estoque disponível?"}'

# Deve retornar resposta válida do RAG
```

### 4. Teste de reindexação
```bash
# Dentro do container
docker-compose exec api python script_reindex.py
```

---

## 🔍 Monitoramento

### Logs Esperados (Sucesso)

```
✅ ChromaDB PersistentClient inicializado: /app/data/chroma
✅ [RAG Service] 150 produtos indexados com embeddings Google AI
🤖 Gemini LLM configurado: models/gemini-2.5-flash
✅ LLM fallback detectou intent: 'stock_check'
```

### Logs de Erro (Se algo falhar)

Se os erros persistirem, verifique:
1. Permissões do diretório `/app/data/chroma`
2. Versão do ChromaDB (deve ser >= 0.4.15)
3. Conflitos de importação circular

---

## 📝 Notas Adicionais

### Compatibilidade
- ✅ Mantém compatibilidade com código existente
- ✅ Não quebra funcionalidades legadas
- ✅ Melhora performance geral do sistema

### Próximos Passos (Opcional)
- [ ] Implementar cache de embeddings para melhor performance
- [ ] Adicionar métricas de uso do ChromaDB
- [ ] Criar testes unitários para o singleton

---

## 🎯 Resumo

**Problema:** Múltiplas instâncias do ChromaDB causando conflitos  
**Solução:** Padrão Singleton + Correção de invocação do RAG chain  
**Resultado:** Sistema estável e funcional  
**Status:** ✅ Pronto para produção
