# Ferramentas dos Agentes - Referência

## Visão Geral

Cada agente no sistema possui acesso a ferramentas específicas que ampliam suas capacidades de análise e tomada de decisão.

## Ferramentas por Agente

### 1. Analista de Demanda

**Ferramentas:**
- `lookup_product`: Busca dados de catálogo e estoque
- `load_demand_forecast`: Carrega previsões do modelo LightGBM
- `python_repl_ast`: Executa análises estatísticas em Python

**Casos de Uso:**
- Análise de tendências de demanda
- Cálculo de médias móveis para prever rupturas
- Identificação de sazonalidade

### 2. Pesquisador de Mercado

**Ferramentas:**
- `scrape_latest_price`: Coleta preços do Mercado Livre
- `tavily_search_results_json`: Busca na web (requer API key)
- `wikipedia`: Busca informações enciclopédicas

**Casos de Uso:**
- Coleta de preços atualizados
- Pesquisa sobre fornecedores e tendências de mercado
- Contextualização sobre produtos ou componentes

### 3. Analista de Logística

**Ferramentas:**
- `compute_distance`: Calcula distâncias geográficas
- `python_repl_ast`: Análises de custo-benefício

**Casos de Uso:**
- Otimização de rotas e custos de transporte
- Cálculo de custo total de aquisição (preço + frete)
- Comparação multi-critério de fornecedores

### 4. Gerente de Compras

**Ferramentas:**
- `python_repl_ast`: Análises financeiras finais

**Casos de Uso:**
- Avaliação de riscos financeiros
- Consolidação de análises anteriores
- Cálculos de ROI e impacto financeiro

## Configuração de APIs Opcionais

### Tavily Search (Recomendado)

Para habilitar buscas avançadas na web:

1. Crie uma conta em https://tavily.com/
2. Obtenha sua API key
3. Adicione ao `.env`:
   ```
   TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxx
   ```

**Benefício:** O agente pode buscar notícias, informações sobre fornecedores e contexto de mercado em tempo real.

### Ferramentas Sempre Disponíveis

- **Wikipedia**: Não requer configuração
- **Python REPL**: Não requer configuração (execução local segura)

## Resiliência e Tratamento de Erros

Todos os agentes foram configurados com:

1. **Graceful Degradation**: Se uma ferramenta falhar, o agente tenta alternativas
2. **Validação de Dados**: Indicação de confiança nas respostas
3. **Fallback Strategies**: Recomendação de revisão manual quando dados são insuficientes

## Logs e Monitoramento

Para verificar quais ferramentas estão sendo usadas:

```bash
docker-compose logs -f worker
```

Busque por linhas com `[tools]` ou nomes de ferramentas específicas.
