# 🏗️ ARQUITETURA MULTI-AGENTE INTEGRADA

## 📋 Visão Geral

Sistema completo de IA multi-agente para análise e recomendação inteligente de compras, integrando:

- **Agente Conversacional** (Gerente): Interface natural com delegação inteligente
- **Time de Especialistas** (4 agentes): Análise aprofundada da cadeia de suprimentos
- **Fontes de Dados**: SQL, RAG, ML, Mercado (Web Search)
- **Ferramentas Avançadas**: Previsões, pesquisa de mercado, comparação de fornecedores

---

## 🎯 Fluxo de Trabalho Completo

```
USUÁRIO
   ↓
📱 "Devo comprar o produto X?"
   ↓
🤖 AGENTE CONVERSACIONAL (Gerente)
   │
   ├─ Pergunta Simples? → Responde diretamente
   │  • "Qual o estoque?" → ProductCatalogTool
   │  • "Previsão de preço?" → get_price_forecast_for_sku
   │
   └─ Pergunta Complexa? → DELEGA ao Time de Especialistas
      ↓
   🏢 TIME DE ESPECIALISTAS (4 agentes)
      │
      ├─ 1️⃣ ANALISTA DE DEMANDA
      │   └─ Determina: "Precisamos comprar?"
      │       • Analisa estoque atual vs mínimo
      │       • Avalia previsões ML de demanda
      │       • Saída: need_restock (true/false)
      │
      ├─ 2️⃣ PESQUISADOR DE MERCADO
      │   └─ Encontra: "Onde e por quanto?"
      │       • find_supplier_offers_for_sku() → Ofertas reais
      │       • search_market_trends_for_product() → Tendências web
      │       • get_price_forecast_for_sku() → Previsões ML
      │       • Saída: Lista de ofertas + contexto de mercado
      │
      ├─ 3️⃣ ANALISTA DE LOGÍSTICA
      │   └─ Otimiza: "Qual fornecedor é melhor?"
      │       • Avalia preço vs confiabilidade vs prazo
      │       • Calcula custo total de aquisição
      │       • compute_distance() → Custos logísticos
      │       • Saída: Fornecedor recomendado
      │
      └─ 4️⃣ GERENTE DE COMPRAS
          └─ Decide: "Aprovar, rejeitar ou revisar?"
              • Consolida todas as análises
              • Avalia riscos (fornecedor único, etc.)
              • Saída: Decisão final + justificativa
      ↓
   💬 RESPOSTA NATURAL ao usuário
      "Recomendo aprovar a compra de 100 unidades 
       com Fornecedor X por R$ 1.500,00..."
```

---

## 🛠️ Componentes Implementados

### FASE 1: Pilares (Modelos + Dados)

#### ✅ 1.1. Modelo de Previsão ML
- **Arquivo**: `app/ml/prediction.py`
- **Status**: Corrigido (normalização de features)
- **Funcionalidade**: Previsão autorregressiva multi-step

#### ✅ 1.2. Fornecedores Sintéticos
- **Arquivo**: `scripts/generate_synthetic_suppliers.py`
- **Novos Modelos**:
  ```python
  # app/models/models.py
  class Fornecedor:
      confiabilidade: float  # 0.0 a 1.0
      prazo_entrega_dias: int  # Dias úteis
  
  class OfertaProduto:
      produto_id: int
      fornecedor_id: int
      preco_ofertado: Decimal
      estoque_disponivel: int
      validade_oferta: datetime
  ```

- **Execução**:
  ```bash
  python scripts/setup_development.py generate_suppliers
  ```

### FASE 2: Ferramentas Avançadas

#### ✅ 2.1. Ferramenta de Previsão ML
```python
# app/agents/tools.py
def get_price_forecast_for_sku(sku: str, days_ahead: int = 7) -> str:
    """
    Obtém previsão de preços futuros para um SKU.
    
    Returns:
        JSON com previsões, tendência (alta/baixa/estável) e métricas
    """
```

**Uso pelos agentes**:
- Agente Conversacional: Respostas rápidas sobre preços futuros
- Pesquisador de Mercado: Contexto para avaliação de ofertas

#### ✅ 2.2. Ferramenta de Pesquisa de Mercado (Tavily)
```python
def search_market_trends_for_product(product_name: str) -> str:
    """
    Pesquisa notícias e análises de mercado que influenciam preços.
    
    Uses:
        Tavily API com search_depth="advanced"
    
    Returns:
        JSON com insights ranqueados por relevância
    """
```

**Configuração**:
```bash
# .env
TAVILY_API_KEY=your_tavily_api_key_here
```

#### ✅ 2.3. Ferramenta de Análise de Fornecedores
```python
def find_supplier_offers_for_sku(sku: str) -> str:
    """
    Busca todas as ofertas de fornecedores para um produto.
    
    Returns:
        JSON com:
        - Lista de ofertas (preço, confiabilidade, prazo)
        - Melhor oferta (balanceada)
        - Preço médio do mercado
    """
```

**Algoritmo de seleção**:
```python
# Penaliza baixa confiabilidade
score = preco * (2 - confiabilidade)
melhor_oferta = min(ofertas, key=lambda x: score)
```

#### ✅ 2.4. Super Ferramenta de Delegação
```python
def run_full_purchase_analysis(sku: str, reason: str) -> str:
    """
    DELEGA ao Time de Especialistas para análise completa.
    
    Quando usar:
    - "Devo comprar o produto X?"
    - "Análise completa para SKU Y"
    - "Recomendação de compra para Z"
    
    Returns:
        Análise consolidada dos 4 especialistas
    """
```

### FASE 3: Hierarquia e Delegação

#### ✅ 3.1. Time de Especialistas Atualizado
- **Arquivo**: `app/agents/supply_chain_team.py`
- **Mudanças**:
  - Pesquisador de Mercado usa novas ferramentas:
    - `find_supplier_offers_for_sku`
    - `search_market_trends_for_product`
    - `get_price_forecast_for_sku`
  - Prompt atualizado com instruções claras

#### ✅ 3.2. Agente Conversacional Promovido
- **Arquivo**: `app/agents/conversational_agent.py`
- **Novo Papel**: Gerente com delegação inteligente
- **Ferramentas**:
  ```python
  tools=[
      ProductCatalogTool(),         # Busca RAG
      get_price_forecast_for_sku,   # Previsão rápida
      run_full_purchase_analysis,   # DELEGAÇÃO
      SupplyChainToolkit(),         # Análises manuais
  ]
  ```

- **Prompt Atualizado**:
  ```
  "Você é um GERENTE experiente com um time de especialistas"
  
  QUANDO DELEGAR:
  - Perguntas complexas: "Devo comprar X?"
  - Recomendações de fornecedor
  - Análises de trade-off
  
  QUANDO RESPONDER DIRETAMENTE:
  - Perguntas simples: "Qual o estoque?"
  - Consultas rápidas de previsão
  - Busca de produtos
  ```

---

## 🚀 Como Usar

### 1. Setup Inicial (uma vez)

```bash
# 1. Criar tabelas no banco
docker compose exec api alembic upgrade head

# Ou executar migration manual:
docker compose exec db psql -U user -d supply_chain -f /migrations/add_supplier_market_features.sql

# 2. Gerar fornecedores e ofertas
docker compose exec api python scripts/setup_development.py generate_suppliers
```

### 2. Conversar com o Sistema

```bash
# Iniciar a API
docker compose up -d

# Acessar chat
http://localhost:3000/agents
```

### 3. Exemplos de Perguntas

#### Perguntas Simples (Resposta Direta)
```
"Qual o estoque do SKU_001?"
"Me mostre produtos da categoria ferramentas"
"Previsão de preço para SKU_001 nos próximos 7 dias?"
```

#### Perguntas Complexas (Delegação ao Time)
```
"Devo comprar o produto SKU_001?"
"Analise a necessidade de reposição para SKU_001"
"Qual fornecedor é melhor para SKU_001?"
"Me dê uma recomendação de compra para SKU_001"
```

---

## 📊 Fluxo de Dados

```
┌──────────────────────────────────────────────────────┐
│           FONTES DE DADOS INTEGRADAS                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  1. 📦 BANCO DE DADOS (PostgreSQL)                  │
│     • Produtos, estoque, vendas                     │
│     • Fornecedores, ofertas                         │
│     • Histórico de preços                           │
│                                                      │
│  2. 🎯 VETORIAL (ChromaDB)                          │
│     • Embeddings de produtos                        │
│     • Busca semântica (RAG)                         │
│                                                      │
│  3. 🤖 MACHINE LEARNING (LightGBM)                  │
│     • Previsões de preços (7-14 dias)              │
│     • Tendências (alta/baixa/estável)               │
│                                                      │
│  4. 🌐 WEB (Tavily API)                             │
│     • Notícias de mercado                           │
│     • Tendências de preço                           │
│     • Análises competitivas                         │
│                                                      │
└──────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────┐
│              CAMADA DE FERRAMENTAS                   │
├──────────────────────────────────────────────────────┤
│  • get_product_info           (RAG)                  │
│  • get_price_forecast_for_sku (ML)                   │
│  • find_supplier_offers       (SQL + JOIN)           │
│  • search_market_trends       (Tavily)               │
│  • run_full_purchase_analysis (Delegação)            │
└──────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────┐
│                  CAMADA DE AGENTES                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  GERENTE (Conversacional)                           │
│     ↓                                                │
│     ├─ Perguntas Simples → Ferramentas diretas      │
│     └─ Perguntas Complexas → Delega ao Time         │
│                              ↓                       │
│                       TIME DE ESPECIALISTAS         │
│                       (4 agentes colaborativos)     │
│                                                      │
└──────────────────────────────────────────────────────┘
                         ↓
                   💬 USUÁRIO
```

---

## 🧪 Testes

### Teste 1: Consulta Simples
```
USUÁRIO: "Qual o estoque de parafusos?"

AGENTE CONVERSACIONAL:
  → Usa ProductCatalogTool (RAG)
  → Resposta direta em 2-3 segundos

ESPERADO: Lista de parafusos com estoque
```

### Teste 2: Previsão Rápida
```
USUÁRIO: "Qual a tendência de preço do SKU_001?"

AGENTE CONVERSACIONAL:
  → Usa get_price_forecast_for_sku
  → Resposta com gráfico de tendência

ESPERADO: "Tendência de ALTA (+5%) nos próximos 7 dias"
```

### Teste 3: Análise Completa (Delegação)
```
USUÁRIO: "Devo comprar 100 unidades do SKU_001?"

AGENTE CONVERSACIONAL:
  1. Detecta pergunta complexa
  2. Informa: "Consultando meu time de especialistas..."
  3. Usa run_full_purchase_analysis(sku="SKU_001", reason="reposição")
     ↓
  TIME DE ESPECIALISTAS executa:
     a) Analista de Demanda → need_restock = true
     b) Pesquisador de Mercado → 5 ofertas encontradas
     c) Analista de Logística → melhor_fornecedor = "X"
     d) Gerente de Compras → decision = "approve"
  4. Retorna resposta consolidada

ESPERADO:
"Recomendo aprovar a compra de 100 unidades.

Fornecedor Recomendado: Distribuidora Nacional
Preço: R$ 1.450,00 (R$ 14,50/un)
Prazo: 5 dias úteis
Confiabilidade: 95%

Justificativa:
- Estoque atual (45 un) abaixo do mínimo (80 un)
- Previsão ML indica tendência de alta (+3%)
- Melhor custo-benefício entre 5 fornecedores

Próximos passos:
- Emitir ordem de compra
- Agendar entrega para +5 dias"
```

---

## 📁 Arquivos Modificados/Criados

### Novos Arquivos
```
scripts/generate_synthetic_suppliers.py    # Gerador de mercado
migrations/add_supplier_market_features.sql  # Migration DB
docs/MULTI_AGENT_ARCHITECTURE.md           # Esta documentação
```

### Arquivos Modificados
```
app/models/models.py                     # +Fornecedor, +OfertaProduto
app/agents/tools.py                      # +4 novas ferramentas
app/agents/supply_chain_team.py          # Prompt atualizado
app/agents/conversational_agent.py       # Delegação implementada
scripts/setup_development.py             # +comando suppliers
```

---

## ⚙️ Configuração Necessária

### 1. Variáveis de Ambiente (.env)
```bash
# Google AI (obrigatório)
GOOGLE_API_KEY=your_google_api_key

# Tavily (opcional, mas recomendado)
TAVILY_API_KEY=your_tavily_api_key

# Database
DATABASE_URL=postgresql://user:password@db:5432/supply_chain
```

### 2. Dependências Python
```bash
# Já no requirements.txt
tavily-python>=0.3.0    # Pesquisa web para agentes
agno>=2.1.3             # Framework de agentes
langchain>=0.2.1        # RAG
lightgbm>=4.0.0         # ML predictions
```

---

## 🎯 Próximos Passos

1. ✅ **CONCLUÍDO**: Implementação completa da arquitetura
2. 🧪 **TESTAR**: Fluxo end-to-end com diferentes cenários
3. 📊 **OTIMIZAR**: Performance das queries de ofertas
4. 🌐 **PRODUÇÃO**: Deploy com rate limiting da Tavily API
5. 📈 **MONITORAR**: Métricas de uso das ferramentas
6. 🔒 **SEGURANÇA**: Validação de inputs dos agentes

---

## 🎓 Referências

- **Agno Framework**: https://docs.agno.com/
- **Tavily API**: https://docs.tavily.com/
- **SQLModel**: https://sqlmodel.tiangolo.com/
- **LightGBM**: https://lightgbm.readthedocs.io/

---

**Status**: ✅ Arquitetura Multi-Agente Implementada e Pronta para Testes  
**Versão**: 1.0.0
