# 🤖 Guia de Validação - Assistente Conversacional Híbrido

## Arquitetura Implementada

### 📐 Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    USUÁRIO (Linguagem Natural)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              CAMADA DE CONVERSAÇÃO (Agno 2.1.3)                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  ConversationalAssistant                                  │  │
│  │  - Gemini 1.5 Flash (temp=0.5 para naturalidade)         │  │
│  │  - Gerencia memória de sessão                            │  │
│  │  - Decide quando acionar ferramentas                     │  │
│  │  - Gera respostas contextuais e amigáveis                │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                CAMADA DE FERRAMENTAS (Agno Tools)               │
│  ┌──────────────────────┐      ┌──────────────────────────┐    │
│  │ ProductCatalogTool   │      │ SupplyChainToolkit       │    │
│  │ (Ponte Agno→RAG)     │      │ (Análises Avançadas)     │    │
│  └──────────┬───────────┘      └──────────────────────────┘    │
└─────────────┼──────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│         CAMADA DE CONHECIMENTO (LangChain + Google AI)          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  RAG Pipeline (LangChain LCEL)                            │  │
│  │  1. Retriever: ChromaDB (top-k=5)                         │  │
│  │  2. Embeddings: Google text-embedding-004 (768 dim)      │  │
│  │  3. Prompt: Template especializado                        │  │
│  │  4. LLM: Gemini Flash (temp=0.0 para precisão)           │  │
│  │  5. Parser: String output                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 🔑 Componentes Principais

#### 1. **RAG Service** (`app/services/rag_service.py`)
- **Framework**: LangChain 0.2.1
- **Embeddings**: Google text-embedding-004
- **Vector Store**: ChromaDB (persistente)
- **LLM**: Gemini 1.5 Flash
- **Função Principal**: `query_product_catalog_with_google_rag(query: str) -> str`

#### 2. **Product Catalog Tool** (`app/agents/tools.py`)
- **Tipo**: `Toolkit` do Agno
- **Método**: `get_product_info(user_question: str) -> str`
- **Papel**: Ponte entre Agno Agent e LangChain RAG

#### 3. **Conversational Agent** (`app/agents/conversational_agent.py`)
- **Função Factory**: `get_conversational_agent(session_id: str) -> Agent`
- **Modelo**: Gemini Flash com `temperature=0.5` (criativo)
- **Ferramentas**: ProductCatalogTool + SupplyChainToolkit
- **Foco**: Instruções detalhadas para conversação natural

---

## 🚀 Passo a Passo de Validação

### PASSO 1: Instalação de Dependências

```bash
# 1. Instalar as novas dependências LangChain
pip install -r requirements.txt

# Ou especificamente:
pip install langchain==0.2.1 langchain-core==0.2.3 langchain-community==0.2.1 langchain-google-genai==1.0.4
```

**Validação**:
```bash
python -c "from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI; print('✅ LangChain Google AI OK')"
```

---

### PASSO 2: Configuração da API Key

Certifique-se de que a variável `GOOGLE_API_KEY` está configurada no arquivo `.env`:

```env
GOOGLE_API_KEY=sua_chave_aqui
```

**Obtenha sua chave em**: https://aistudio.google.com/app/apikey

**Validação**:
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ API Key OK' if os.getenv('GOOGLE_API_KEY') else '❌ API Key ausente')"
```

---

### PASSO 3: Reset do ChromaDB (IMPORTANTE)

Como mudamos a estrutura do RAG para usar LangChain, é **crítico** limpar o banco vetorial antigo:

```bash
# Opção 1: Deletar diretório (se estiver fora do Docker)
rm -rf data/chroma

# Opção 2: Se estiver usando Docker
docker-compose exec api rm -rf /app/data/chroma
```

**Por quê?** O novo RAG usa uma estrutura de documentos diferente (LangChain `Document` vs ChromaDB puro).

---

### PASSO 4: Reindexação do Catálogo

Execute o script de reindexação para popular o ChromaDB com a nova estrutura:

**Opção A**: Se tiver um endpoint/script de inicialização
```bash
# Verificar se existe um script de setup
python -m app.scripts.index_products  # (ajustar conforme seu projeto)
```

**Opção B**: Via Python direto (criar script temporário se necessário)
```python
# script_reindex.py
from app.core.database import engine
from app.services.rag_service import index_product_catalog
from sqlmodel import Session

with Session(engine) as session:
    index_product_catalog(session)
    print("✅ Catálogo reindexado com LangChain + Google AI")
```

Execute:
```bash
python script_reindex.py
```

**Validação**:
Deve aparecer no console:
```
✅ [RAG Service] X produtos indexados com embeddings Google AI
```

---

### PASSO 5: Teste Isolado do RAG Service

Antes de testar o agente completo, valide que o RAG está funcionando:

**Criar**: `test_rag_service.py`
```python
from app.services.rag_service import query_product_catalog_with_google_rag

# Teste 1: Pergunta direta
print("\n=== TESTE 1: Pergunta Direta ===")
response = query_product_catalog_with_google_rag("Qual o estoque da parafusadeira Makita?")
print(response)

# Teste 2: Pergunta por SKU
print("\n=== TESTE 2: Pergunta por SKU ===")
response = query_product_catalog_with_google_rag("Me fale sobre o produto SKU_005")
print(response)

# Teste 3: Pergunta por categoria
print("\n=== TESTE 3: Pergunta por Categoria ===")
response = query_product_catalog_with_google_rag("Quais ferramentas elétricas temos?")
print(response)

# Teste 4: Produto inexistente
print("\n=== TESTE 4: Produto Inexistente ===")
response = query_product_catalog_with_google_rag("Tem máquina de solda MIG 350?")
print(response)
```

Execute:
```bash
python test_rag_service.py
```

**Resultado Esperado**:
- Respostas baseadas no catálogo real
- Menção de SKUs quando relevante
- Informações de estoque precisas
- Resposta educada quando produto não encontrado

---

### PASSO 6: Teste da ProductCatalogTool

Valide a ferramenta Agno isoladamente:

**Criar**: `test_product_tool.py`
```python
from app.agents.tools import ProductCatalogTool

tool = ProductCatalogTool()

# Teste 1: Pergunta natural
print("\n=== TESTE 1: Pergunta Natural ===")
result = tool.get_product_info("Tem serra circular no estoque?")
print(result)

# Teste 2: Pergunta técnica
print("\n=== TESTE 2: Pergunta Técnica ===")
result = tool.get_product_info("Quantas unidades da SKU_001 temos disponíveis?")
print(result)

# Teste 3: Múltiplos produtos
print("\n=== TESTE 3: Múltiplos Produtos ===")
result = tool.get_product_info("Me mostre todos os produtos da Bosch")
print(result)
```

Execute:
```bash
python test_product_tool.py
```

**Resultado Esperado**:
- Logs mostrando `[Product Catalog Tool] Buscando informações...`
- Respostas detalhadas e contextualizadas
- Sem erros de importação ou execução

---

### PASSO 7: Teste do Agente Conversacional Completo

Este é o teste **mais importante** - valida a conversação natural end-to-end:

**Criar**: `test_conversational_agent.py`
```python
from app.agents.conversational_agent import get_conversational_agent

# Criar agente para uma sessão
agent = get_conversational_agent(session_id="test_123")

print("🤖 Assistente Conversacional Iniciado!\n")
print("=" * 60)

# CENÁRIO 1: Pergunta Direta
print("\n📝 CENÁRIO 1: Pergunta Direta")
print("USER: Qual o estoque da Serra Mármore Bosch?")
response = agent.run("Qual o estoque da Serra Mármore Bosch?")
print(f"ASSISTANT: {response.content}\n")
print("-" * 60)

# CENÁRIO 2: Pergunta Indireta
print("\n📝 CENÁRIO 2: Pergunta Indireta")
print("USER: Vocês trabalham com furadeiras da Makita?")
response = agent.run("Vocês trabalham com furadeiras da Makita?")
print(f"ASSISTANT: {response.content}\n")
print("-" * 60)

# CENÁRIO 3: Pergunta Fragmentada (contexto)
print("\n📝 CENÁRIO 3: Pergunta Fragmentada (requer contexto)")
print("USER: E a lixadeira orbital?")
response = agent.run("E a lixadeira orbital?")
print(f"ASSISTANT: {response.content}\n")
print("-" * 60)

# CENÁRIO 4: Produto Inexistente
print("\n📝 CENÁRIO 4: Produto Inexistente")
print("USER: Tem a máquina de solda MIG 350?")
response = agent.run("Tem a máquina de solda MIG 350?")
print(f"ASSISTANT: {response.content}\n")
print("-" * 60)

# CENÁRIO 5: Pergunta por Categoria
print("\n📝 CENÁRIO 5: Pergunta por Categoria")
print("USER: Quais produtos da categoria ferramentas temos?")
response = agent.run("Quais produtos da categoria ferramentas temos?")
print(f"ASSISTANT: {response.content}\n")
print("-" * 60)

print("\n✅ Testes Concluídos!")
```

Execute:
```bash
python test_conversational_agent.py
```

**O que Observar**:
1. **Acionamento de Ferramentas**: Logs mostrando `[Product Catalog Tool]` sendo chamada
2. **Naturalidade**: Respostas completas, não apenas dados brutos
3. **Contexto**: Agente entende pronomes e contexto (quando possível)
4. **Emojis e Formatação**: Respostas com markdown e emojis ocasionais
5. **Fallback Educado**: Quando produto não existe, resposta gentil

**Critérios de Sucesso** ✅:
- ✅ Agente aciona `ProductCatalogTool` automaticamente para perguntas sobre produtos
- ✅ Respostas são fluidas e naturais (não robotizadas)
- ✅ Informações corretas do catálogo
- ✅ SKU mencionado quando relevante
- ✅ Sem erros de execução

---

### PASSO 8: Teste Interativo (Conversação Real)

Para uma validação completa da experiência do usuário:

**Criar**: `interactive_chat.py`
```python
from app.agents.conversational_agent import get_conversational_agent

def main():
    print("🤖 Assistente de Compras Inteligente")
    print("=" * 60)
    print("Digite suas perguntas naturalmente. Use 'sair' para encerrar.\n")
    
    session_id = "interactive_001"
    agent = get_conversational_agent(session_id)
    
    while True:
        user_input = input("🧑 VOCÊ: ").strip()
        
        if user_input.lower() in ['sair', 'exit', 'quit']:
            print("\n👋 Até logo!")
            break
        
        if not user_input:
            continue
        
        try:
            response = agent.run(user_input)
            print(f"\n🤖 ASSISTENTE: {response.content}\n")
            print("-" * 60)
        except Exception as e:
            print(f"\n❌ Erro: {e}\n")

if __name__ == "__main__":
    main()
```

Execute:
```bash
python interactive_chat.py
```

**Diálogos Sugeridos para Testar**:

1. **Fluxo Natural**:
   ```
   VOCÊ: Oi, tudo bem?
   ASSISTENTE: [saudação amigável]
   
   VOCÊ: Tem parafusadeira no estoque?
   ASSISTENTE: [busca e responde com detalhes]
   
   VOCÊ: E qual o preço dela?
   ASSISTENTE: [usa contexto do produto anterior]
   ```

2. **Perguntas Variadas**:
   ```
   - "Quantas serras temos disponíveis?"
   - "Me fale sobre os produtos da Makita"
   - "Estou precisando de furadeiras, o que vocês têm?"
   - "Qual o SKU da lixadeira?"
   ```

3. **Testes de Limite**:
   ```
   - "Tem unicórnio mecânico?" (produto inexistente)
   - "Preciso comprar 1000 parafusos" (quantidade específica)
   ```

---

## 🔍 Checklist de Validação Final

### Arquitetura
- [ ] LangChain instalado e funcionando
- [ ] Google API Key configurada
- [ ] ChromaDB resetado e reindexado
- [ ] Embeddings Google AI gerando vetores

### RAG Service
- [ ] `query_product_catalog_with_google_rag()` retorna respostas corretas
- [ ] Busca semântica encontra produtos relevantes
- [ ] Prompt template gera respostas naturais
- [ ] Fallback funciona quando produto não existe

### Product Catalog Tool
- [ ] Ferramenta registrada no Toolkit do Agno
- [ ] `get_product_info()` chama o RAG corretamente
- [ ] Logs de debug aparecem no console
- [ ] Tratamento de erros funciona

### Conversational Agent
- [ ] Agente criado com `get_conversational_agent()`
- [ ] Instruções de conversação natural carregadas
- [ ] Ferramentas disponíveis (ProductCatalogTool + SupplyChainToolkit)
- [ ] `show_tool_calls=True` mostra debug das ferramentas
- [ ] Temperatura 0.5 gera respostas variadas mas coerentes

### Experiência do Usuário (CRÍTICO)
- [ ] Usuário NÃO precisa usar comandos específicos
- [ ] Perguntas informais funcionam ("e a parafusadeira?")
- [ ] Respostas são completas, não apenas dados brutos
- [ ] Emojis e formatação Markdown presentes
- [ ] Contexto mantido entre perguntas (quando possível)
- [ ] Fallback educado quando informação não encontrada

---

## 🐛 Troubleshooting

### Problema: "GOOGLE_API_KEY não encontrada"
**Solução**:
1. Verifique o arquivo `.env`
2. Reinicie a aplicação após adicionar a chave
3. No Docker: `docker-compose restart api`

### Problema: "Erro ao consultar catálogo"
**Solução**:
1. Verifique se o ChromaDB foi reindexado
2. Confirme que existem produtos no banco
3. Teste o RAG service isoladamente

### Problema: "Agente não aciona ferramentas"
**Solução**:
1. Verifique os logs (`show_tool_calls=True`)
2. As instruções do agente devem enfatizar o uso das ferramentas
3. Certifique-se que a pergunta realmente envolve produtos

### Problema: "Respostas genéricas ou robotizadas"
**Solução**:
1. Ajuste a temperatura do modelo (atual: 0.5)
2. Revise as instruções para enfatizar naturalidade
3. Use `get_gemini_for_creative()` em vez de modelo padrão

### Problema: "Dimensão incompatível no ChromaDB"
**Solução**:
1. Delete completamente o diretório `data/chroma`
2. Reindexe do zero
3. Google embeddings usa 768 dimensões, não 384

---

## 📊 Métricas de Sucesso

### Conversação Natural (Objetivo Principal)
- **Meta**: 90%+ das perguntas naturais são compreendidas
- **Teste**: Perguntas informais sem comandos
- **Validação**: Agente aciona ferramenta correta sem precisar reformular

### Precisão das Respostas
- **Meta**: 95%+ das informações corretas quando produto existe
- **Teste**: Comparar resposta com dados do banco
- **Validação**: SKU, estoque e categoria corretos

### Latência
- **Meta**: < 5 segundos por resposta (rede + LLM + RAG)
- **Teste**: Cronometrar requisições
- **Validação**: Usar `time.time()` antes/depois

### Naturalidade
- **Meta**: Respostas lidas como texto humano, não lista de dados
- **Teste**: Leitura subjetiva
- **Validação**: Presença de conectivos, contexto, emojis ocasionais

---

## 🎯 Próximos Passos (Pós-Validação)

### 1. Integração com Interface Web
Conectar o agente ao endpoint FastAPI existente.

### 2. Melhorias de Memória
Implementar memória persistente entre sessões usando Redis ou banco.

### 3. Analytics
Rastrear quais perguntas são mais comuns e taxa de sucesso.

### 4. Tuning de Prompts
Ajustar instruções baseado em feedback real de usuários.

### 5. Multilíngua
Expandir para suportar outras línguas se necessário.

---

## 📚 Referências

- **Agno Docs**: https://docs.agno.com/
- **LangChain Docs**: https://docs.langchain.com/oss/python/langchain/overview
- **Google AI Docs**: https://ai.google.dev/
- **ChromaDB**: https://docs.trychroma.com/

---

## ✅ Conclusão

Quando todos os testes acima passarem, você terá um **assistente conversacional híbrido** funcionando com:

✅ **Agno** gerenciando a conversa
✅ **LangChain** fornecendo RAG preciso
✅ **Google AI** unificando LLM e embeddings
✅ **Conversação natural** sem necessidade de comandos

**Sucesso = Usuário conversa naturalmente e o sistema busca informações de forma autônoma!** 🎉
