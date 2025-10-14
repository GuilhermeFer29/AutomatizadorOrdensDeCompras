# 🤖 Assistente Conversacional Híbrido - Quick Start

## 🎯 Visão Geral

Assistente de conversação **excepcionalmente natural** construído com arquitetura híbrida que combina:

- **Agno 2.1.3**: Gerencia diálogo, memória e decisões
- **LangChain 0.2.1**: Pipeline RAG para busca precisa de informações
- **Google AI**: LLM (Gemini Flash) + Embeddings (text-embedding-004)

### 💡 Diferencial

O usuário **NÃO precisa aprender comandos** ou falar de forma robotizada. 
Apenas converse naturalmente e o agente busca informações autonomamente.

**Exemplo**:
```
👤 Você: Tem parafusadeira no estoque?
🤖 Assistente: Sim! Encontrei 3 modelos de parafusadeiras...
              - Parafusadeira Makita (SKU_005): 45 unidades
              - Parafusadeira Bosch GSR (SKU_003): 28 unidades
              ...

👤 Você: E da Makita, qual o preço?
🤖 Assistente: [busca automaticamente informações da SKU_005]
```

---

## 🚀 Setup Rápido (5 minutos)

### 1️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

Isso instala:
- `langchain==0.2.1`
- `langchain-core==0.2.3`
- `langchain-community==0.2.1`
- `langchain-google-genai==1.0.4`

### 2️⃣ Configurar Google API Key

No arquivo `.env`:
```env
GOOGLE_API_KEY=sua_chave_aqui
```

**Obtenha gratuitamente em**: https://aistudio.google.com/app/apikey

### 3️⃣ Reindexar Catálogo

```bash
python script_reindex.py
```

Este script:
- ✅ Valida ambiente e API Key
- ✅ Limpa ChromaDB antigo (opcional)
- ✅ Indexa produtos com embeddings Google AI
- ✅ Verifica se RAG está funcionando

### 4️⃣ Testar!

**Opção A - Testes Automatizados**:
```bash
python test_hybrid_architecture.py
```

**Opção B - Chat Interativo**:
```bash
python interactive_chat.py
```

---

## 📁 Arquivos Criados/Modificados

### ✅ Novos Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `GUIA_VALIDACAO_ASSISTENTE_CONVERSACIONAL.md` | Documentação completa da arquitetura e validação |
| `test_hybrid_architecture.py` | Suite de testes automatizados |
| `interactive_chat.py` | Interface de chat interativo |
| `script_reindex.py` | Script de reindexação do catálogo |
| `README_ASSISTENTE_CONVERSACIONAL.md` | Este arquivo (quick start) |

### 🔧 Arquivos Modificados

| Arquivo | Mudanças |
|---------|----------|
| `requirements.txt` | Adicionadas dependências LangChain |
| `app/services/rag_service.py` | Refatorado para LangChain + Google AI |
| `app/agents/tools.py` | Adicionada `ProductCatalogTool` |
| `app/agents/conversational_agent.py` | Criada função `get_conversational_agent()` |

---

## 🏗️ Arquitetura em 3 Camadas

```
┌──────────────────────────────────────┐
│   Usuário (Linguagem Natural)        │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  CAMADA 1: Conversação (Agno)        │
│  • Gemini Flash (temp=0.5)           │
│  • Memória de sessão                 │
│  • Decisão de ferramentas            │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  CAMADA 2: Ferramentas (Agno Tools)  │
│  • ProductCatalogTool ──────┐        │
│  • SupplyChainToolkit       │        │
└─────────────────────────────┼────────┘
                              │
                              ▼
                    ┌─────────────────────────┐
                    │  CAMADA 3: RAG          │
                    │  • LangChain Pipeline   │
                    │  • Google Embeddings    │
                    │  • ChromaDB             │
                    │  • Gemini Flash (LLM)   │
                    └─────────────────────────┘
```

### Fluxo de uma Pergunta

1. **Usuário pergunta**: "Tem parafusadeira Makita?"
2. **Agno Agent**: Entende intenção → Aciona `ProductCatalogTool`
3. **ProductCatalogTool**: Chama `query_product_catalog_with_google_rag()`
4. **LangChain RAG**:
   - Gera embedding da pergunta (Google AI)
   - Busca top-5 produtos relevantes (ChromaDB)
   - Monta prompt com contexto
   - LLM gera resposta (Gemini Flash)
5. **Agno Agent**: Recebe resposta → Formata de forma amigável
6. **Usuário recebe**: Resposta completa e contextualizada

---

## 🧪 Testes Disponíveis

### 1. Suite Completa
```bash
python test_hybrid_architecture.py
```

Testa:
- ✅ Imports e dependências
- ✅ Google API Key
- ✅ RAG Service (LangChain)
- ✅ Product Catalog Tool
- ✅ Agente Conversacional

### 2. Chat Interativo
```bash
python interactive_chat.py
```

Comandos no chat:
- `ajuda` - Mostra comandos
- `exemplos` - Mostra perguntas de exemplo
- `limpar` - Limpa tela
- `sair` - Encerra

### 3. Teste Manual de Componentes

**RAG Service**:
```python
from app.services.rag_service import query_product_catalog_with_google_rag

response = query_product_catalog_with_google_rag("Quais produtos temos?")
print(response)
```

**Product Catalog Tool**:
```python
from app.agents.tools import ProductCatalogTool

tool = ProductCatalogTool()
result = tool.get_product_info("Tem serra circular?")
print(result)
```

**Agente Conversacional**:
```python
from app.agents.conversational_agent import get_conversational_agent

agent = get_conversational_agent(session_id="test_001")
response = agent.run("Qual o estoque da parafusadeira?")
print(response.content)
```

---

## 📝 Exemplos de Uso

### Perguntas Naturais Suportadas

✅ **Consultas de Estoque**:
- "Tem parafusadeira no estoque?"
- "Quantas serras circulares temos?"
- "Qual o estoque da SKU_005?"

✅ **Busca de Produtos**:
- "Quais produtos da Makita temos?"
- "Me fale sobre ferramentas elétricas"
- "Tem furadeira da Bosch?"

✅ **Análises**:
- "Precisa comprar mais parafusos?"
- "Análise de demanda da SKU_001"
- "Qual o preço da lixadeira?"

✅ **Conversação Contextual**:
- "E a serra mármore?" (após falar de outro produto)
- "Quanto tem dela?" (referência ao último produto)
- "E o preço?" (contexto da conversa)

---

## 🎨 Características da Conversação

### ✨ O que o Agente Faz Automaticamente

- 🔍 **Busca proativa**: Aciona ferramentas sem pedir permissão
- 🧠 **Entende contexto**: Resolve pronomes e referências
- 📊 **Interpreta dados**: Não apenas repassa informações brutas
- 💬 **Tom amigável**: Emojis ocasionais e formatação Markdown
- ⚡ **Respostas rápidas**: Perguntas simples = respostas diretas

### 🚫 O que NÃO É Necessário

- ❌ Comandos especiais (`/buscar`, `!produto`, etc.)
- ❌ Sintaxe específica
- ❌ Mencionar explicitamente ferramentas
- ❌ Falar de forma robotizada

---

## 🔧 Troubleshooting

### Problema: "GOOGLE_API_KEY não encontrada"
```bash
# Verifique o .env
cat .env | grep GOOGLE_API_KEY

# Se vazio, adicione
echo "GOOGLE_API_KEY=sua_chave" >> .env
```

### Problema: "Erro ao consultar catálogo"
```bash
# Reindexe o catálogo
python script_reindex.py
```

### Problema: "ModuleNotFoundError: langchain"
```bash
# Reinstale dependências
pip install -r requirements.txt
```

### Problema: "ChromaDB dimension mismatch"
```bash
# Delete e reindexe
rm -rf data/chroma
python script_reindex.py
```

---

## 📚 Documentação Completa

Para detalhes completos, consulte:

- **GUIA_VALIDACAO_ASSISTENTE_CONVERSACIONAL.md**: Arquitetura, validação detalhada, métricas
- **Código-fonte comentado**: Todos os arquivos possuem docstrings completas

### Referências Oficiais

- 🔗 **Agno**: https://docs.agno.com/
- 🔗 **LangChain**: https://docs.langchain.com/oss/python/langchain/overview
- 🔗 **Google AI**: https://ai.google.dev/

---

## ✅ Checklist de Sucesso

Sua implementação está funcionando se:

- [ ] `python test_hybrid_architecture.py` passa todos os testes
- [ ] `python interactive_chat.py` inicia sem erros
- [ ] Perguntas naturais acionam `ProductCatalogTool` automaticamente
- [ ] Respostas são fluidas e contextualizadas (não apenas dados)
- [ ] SKU é mencionado quando relevante
- [ ] Fallback educado quando produto não existe

---

## 🎉 Próximos Passos

Após validar a implementação:

1. **Integração Web**: Conectar ao endpoint FastAPI existente
2. **Memória Persistente**: Usar Redis para contexto entre sessões
3. **Analytics**: Rastrear perguntas frequentes e taxa de sucesso
4. **Tuning**: Ajustar prompts baseado em feedback real
5. **Multilíngua**: Expandir suporte a idiomas

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Consulte **GUIA_VALIDACAO_ASSISTENTE_CONVERSACIONAL.md** (seção Troubleshooting)
2. Execute `python test_hybrid_architecture.py` para diagnóstico
3. Verifique logs detalhados com `show_tool_calls=True`

---

**🚀 Divirta-se conversando naturalmente com seu assistente inteligente!**
