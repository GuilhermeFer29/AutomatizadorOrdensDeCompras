# COPILOT PROJECT MEMORY (DO NOT DELETE)

## Project Info

name: "Plataforma Preditiva - Backend Assíncrono"
repo_root: "/workspace/repo"

## Product Vision

Objetivo Final: Desenvolver um **Agente de IA para Automação da Cadeia de Suprimentos**.

- Foco inicial: **Automação Inteligente de Ordens de Compra para Pequenas e Médias Indústrias**.
- O sistema deve monitorar estoque, prever demanda, identificar melhores fornecedores e gerar pedidos automaticamente.
- Público-alvo: **Profissionais de Compras** → o sistema apoia suas decisões, reduz trabalho manual e aumenta ROI.
- Impacto esperado: Redução de custos, aumento de eficiência e prevenção de rupturas na produção.

## Persona Context

role: "Desenvolvedor Python Sênior"
focus:

- FastAPI
- Celery + Redis
- Docker Compose
- SQLModel
- MLOps básico (Prophet)
- CrewAI
  rules:
- Sempre usar docker-compose com serviços api, db, broker
- Sempre usar type hints em funções públicas
- Retornar arquivos completos, não apenas snippets
- Broker/Backend Redis: "redis://broker:6379/0"
- Docker-compose: db = MySQL, volumes nomeados = postgres_data
- Não avançar de fase sem validação `PASS`
- Não adicionar dependências fora do Plano de Ação
- Reescrever fases anteriores apenas se falharem

## Current Phase

phase: 5
status: "PENDING"

## Phase Checklist

0: PASS
1: PASS
2: PASS
3: PENDING
4: PASS
4.5: PASS
5: PENDING

---

## Phase 0 — Estrutura inicial

- [x] Criar `.env` com placeholders (DATABASE_URL, REDIS_URL, MYSQL_ROOT_PASSWORD, etc.)
- [x] Criar `docker-compose.yml` básico (api, db, broker)
- [x] Criar `requirements.txt` ou `pyproject.toml` com dependências mínimas
- [x] Criar estrutura de pastas `app/core`, `app/models`, `app/routers`, `app/services`, `app/tasks`, `app/ml`, `scripts`
- [x] Validação: `tree -L 2` mostrando diretórios
- Status: PASS

---

## Phase 1 — API base + Celery + Docker

- [x] `docker-compose.yml` completo com db/mysql + broker/redis + volume postgres_data
- [x] `app/core/celery_app.py` criado
- [x] `app/tasks/debug_tasks.py` criado
- [x] `app/services/task_service.py` criado
- [x] `app/routers/tasks_router.py` criado
- [x] `app/main.py` criado (registrando rotas + startup hook)
- [x] Validação:
      command: |
      docker-compose up --build
      docker-compose exec api celery -A app.core.celery_app worker --loglevel=info
      curl -X POST http://localhost:8000/tasks/test
      expected_log_excerpt: "Task long_running_task[...] succeeded"
      result: PASS
- Status: PASS

---

## Phase 2 — Banco de Dados e Models

- [x] Criar `app/core/database.py` com engine lendo `DATABASE_URL` do .env
- [x] Criar `app/models/models.py` com modelos SQLModel: - Produto - VendasHistoricas - PrecosHistoricos - ModeloPredicao
- [x] Implementar `create_db_and_tables()` no `main.py`
- [x] Validar conexão e criação de tabelas:
      command: |
      docker compose exec api python -m compileall app
      docker compose exec db mysql -u app_user -papp_password -e "SHOW TABLES IN app_db;"
      expected_result: - CompileAll sem erros - Tabelas `produtos`, `vendas_historicas`, `precos_historicos`, `modelos_predicao` presentes
- Status: PASS

---

## Phase 3 — MLOps + Dashboards (retrain com dados do Scraping)

- [x] Criar `scripts/seed_database.py` (opcional: popular DB inicial com CSV histórico, mas usar dados de `PrecosHistoricos` como fonte principal).
- [x] Criar `app/ml/training.py`: - Função `train_prophet_model(produto_id: int) -> str` - Lê dados de preços de `PrecosHistoricos` para o produto. - Treina modelo Prophet. - Salva modelo (`/models/{produto_id}.pkl`) e relatório PDF (`/reports/{produto_id}.pdf`).
- [x] Criar `app/services/email_service.py`: - Função `send_training_report(to_email: str, produto_id: int, pdf_path: str) -> None` - Envia e-mail corporativo com PDF anexo e corpo estruturado.
- [x] Criar `app/tasks/ml_tasks.py`: - Tarefa Celery `retrain_model_task(produto_id: int)` que: 1. Executa `train_prophet_model`. 2. Gera relatório PDF. 3. Chama `send_training_report`.
- [x] Criar rota `/vendas/retrain/{produto_id}`: - Dispara retraining para produto específico.
- [x] Criar dashboard simples (Streamlit ou FastAPI + template frontend): - Página `/dashboard`: - Exibe gráfico histórico de preços (dados de `PrecosHistoricos`). - Exibe previsão do Prophet (curva futura). - Exibe métricas (MSE/RMSE).
- [x] Validação:
      command: |
      docker-compose up --build
      docker-compose exec api celery -A app.core.celery_app worker --loglevel=info
      curl -X POST http://localhost:8000/vendas/retrain/1
      expected_result: - Worker processa tarefa `retrain_model_task` - Modelo salvo em `/models/` - Relatório PDF gerado em `/reports/` - E-mail enviado com PDF - Dashboard acessível em `/dashboard` mostrando histórico + previsão
- Status: PENDING

---

## Phase 4 — Scraping com ScraperAPI (Mercado Livre)

- [x] Criar `app/scraping/scrapers.py`: - Função `scrape_mercadolivre(produto_nome: str) -> Optional[float]` - Usa **ScraperAPI** (`http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={target_url}`) - Faz parsing com BeautifulSoup4. - Implementa retry com `tenacity` (backoff exponencial) e timeout. - Retorna preço como `float` ou `None`.
- [x] Criar `app/services/scraping_service.py`: - Função `scrape_and_save_price(produto_id: int) -> None` - Busca nome do produto no DB. - Chama `scrape_mercadolivre`. - Persiste preço em `PrecosHistoricos`.
- [x] Criar `app/tasks/scraping_tasks.py`: - Tarefa Celery `scrape_product(produto_id: int)` - Tarefa Celery `scrape_all_products()` - Ambas chamam `scraping_service`.
- [x] Atualizar `app/core/celery_app.py`: - Configurar `beat_schedule` com `crontab(hour="*/8")` para rodar `scrape_all_products` a cada 8h.
- [x] Atualizar `docker-compose.yml`: - Adicionar serviço `beat` rodando Celery Beat.
- [x] Adicionar variável no `.env`: - `SCRAPERAPI_KEY=...`
- [x] Validação:
      command: |
      docker-compose up --build
      docker-compose exec api celery -A app.core.celery_app worker --loglevel=info
      docker-compose exec api celery -A app.core.celery_app beat --loglevel=info
      expected_result: - Worker executa `scrape_all_products` automaticamente a cada 8h - Logs mostram produtos sendo raspados do Mercado Livre - Novos preços aparecem na tabela `PrecosHistoricos`
      result: - PASS — Serviços `api`, `worker` e `beat` iniciados via `docker compose` (contornando erro gRPC build) - Scraping validado manualmente (`scrape_mercadolivre` e `scrape_and_save_price`) com registros persistidos - Logs do worker confirmam registro das tarefas `app.tasks.scraping.*`
- Status: PASS

---

## Phase 4.5 — Integração com APIs Públicas de Localização e Fornecedores

- [x] Criar `app/services/cep_service.py`: - Função `get_address_from_cep(cep: str) -> Dict[str, str]` usando **ViaCEP** (gratuito, sem API key).
- [x] Criar `app/services/geolocation_service.py`: - Função `get_coordinates_from_address(address: str) -> Tuple[float, float]` usando **Nominatim (OpenStreetMap)**. - Função `calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float` (fórmula de Haversine).
- [x] Enriquecer `Fornecedor` no DB com: - CEP - Latitude/Longitude
- [x] Criar lógica no serviço de pedidos: - Ao gerar ordem de compra, comparar fornecedores: - Pelo preço - Pelo prazo - Pela **proximidade geográfica** (distância). - Regra: em caso de **urgência**, priorizar fornecedor mais próximo.
- [x] Criar endpoint `/fornecedores/enriquecer` para atualizar fornecedores com dados de CEP/geo.
- [x] Observações: - Esses dados poderão ser usados no futuro: - Como **feature no modelo preditivo** (prazo de entrega estimado considerando distância). - Como **contexto no CrewAI** para análise multi-agente.
- [x] Validação:
  - Seed inicial de fornecedores com CEPs.
  - Rodar enriquecimento (`/fornecedores/enriquecer`).
  - Gerar pedido com urgência → sistema deve escolher fornecedor mais próximo.
  - Logs devem mostrar cálculo de distância e fornecedor selecionado.
- Status: PASS

---

Ótima ideia. Preparar um bom prompt para o Copilot e um checklist detalhado é a melhor forma de garantir que o desenvolvimento da Fase 5 seja estruturado e siga o plano "uma coisa de cada vez".

Abaixo estão o prompt que você pode usar para guiar o Copilot e, em seguida, o bloco de markdown para adicionar ao seu arquivo de controle de projeto (.copilot\_.md).

1. Prompt para o Copilot (Fase 5 - LangChain)
   Aqui está um prompt completo que você pode usar para iniciar a Fase 5 com o Copilot. Ele estabelece o contexto, o objetivo e as regras para esta nova etapa.

Markdown

# CONTEXTO ATUAL

Estamos iniciando a **Fase 5** do projeto "Plataforma Preditiva - Backend Assíncrono". A arquitetura base com FastAPI, Celery, SQLModel e serviços modulares já está robusta e funcional. As fases anteriores garantiram a coleta de dados (scraping), o treinamento de modelos de previsão (Prophet) e a exposição de dados via API e dashboard.

Decidimos usar **LangChain**, especificamente o módulo **LangGraph**, para construir a camada de inteligência que orquestrará os serviços existentes, em vez do CrewAI.

**PERSONA:**
Você continua atuando como um Desenvolvedor Python Sênior, especialista em FastAPI, Celery, SQLModel, e agora com foco em **LangChain e LangGraph** para a criação de sistemas de múltiplos agentes.

# OBJETIVO DA FASE 5

Implementar um sistema de agentes de IA colaborativos usando LangChain e LangGraph para automatizar a análise e recomendação de ordens de compra. A equipe de agentes deve seguir este fluxo:

1.  **Analista de Demanda:** Verifica a necessidade de reposição de um produto com base no estoque atual e na previsão de demanda futura.
2.  **Pesquisador de Mercado:** Se a reposição for necessária, busca os preços atuais do produto em diferentes fornecedores.
3.  **Analista de Logística:** Avalia as opções de fornecedores com base em custo total (preço + frete estimado por distância).
4.  **Gerente de Compras (Agente Final):** Consolida todas as informações e gera uma recomendação final de compra estruturada.

# INSTRUÇÕES PARA ESTA FASE

1.  **Crie o Módulo de Agentes:** Inicie criando o diretório `app/agents/`.
2.  **Defina as Ferramentas (`Tools`):** Crie o arquivo `app/agents/tools.py`. Importe os serviços existentes (ex: `scraping_service`, `ml_service`) e encapsule suas funções como `Tools` do LangChain. As ferramentas devem ter descrições claras para que o LLM saiba como usá-las.
3.  **Construa o Grafo de Agentes:** Crie o arquivo `app/agents/supply_chain_graph.py`.
    - Defina o `State` do grafo (`TypedDict`) para carregar as informações entre os nós (ex: `product_sku`, `forecast`, `market_prices`, `recommendation`).
    - Implemente cada agente como um "nó" (`node`) no grafo. Cada nó será uma função que invoca um LLM com suas ferramentas e atualiza o estado.
    - Use `StateGraph` do LangGraph para montar o fluxo, definindo o ponto de entrada e as arestas (`edges`) que conectam os agentes em sequência.
4.  **Integre com a API:**
    - Crie um novo serviço `app/services/agent_service.py` que encapsula a lógica para invocar o grafo compilado.
    - Crie um novo router `app/routers/agent_router.py` com um endpoint `/agents/execute-analysis/{sku}` que dispara o serviço.
5.  **Validação:** O objetivo final é que o endpoint retorne um JSON com a recomendação final, incluindo o fornecedor escolhido, o preço e a justificativa.

Siga o checklist da Fase 5 e entregue um passo de cada vez para validação. 2. Checklist da Fase 5 para o .copilot*.md
Copie e cole este bloco de markdown no final do seu arquivo .copilot*.md (ou similar) para acompanhar o progresso desta fase.

Markdown

---

---

## Phase 5 — Agentes com LangChain

- [ ] **Configuração do Ambiente:** - [ ] Adicionar `langchain`, `langgraph`, `langchain-community`, `langchain-openai`, `openrouter-python` ao `requirements.txt`. - [ ] Criar o diretório `app/agents/` e o arquivo `__init__.py`. - [ ] Adicionar `OPENROUTER_API_KEY` e `OPENROUTER_MODEL_NAME` ao arquivo `.env`.

- [ ] **Definição das Ferramentas:** - [ ] Criar o arquivo `app/agents/tools.py`. - [ ] Implementar a primeira ferramenta: `search_market_price(product_sku: str)`, que usa o `scraping_service` e retorna o preço atual. - [ ] Implementar a segunda ferramenta: `get_product_info(product_sku: str)`, que consulta o banco de dados e retorna o estoque atual e mínimo.

- [ ] **Construção do Grafo (Parte 1 - Nós Iniciais):** - [ ] Criar o arquivo `app/agents/supply_chain_graph.py`. - [ ] Definir a classe de estado `PurchaseAnalysisState(TypedDict)`. - [ ] Implementar o primeiro nó: `demand_analyst_node`, que usa a ferramenta `get_product_info` e decide se a compra é necessária (lógica: `estoque_atual <= estoque_minimo`). - [ ] Implementar o segundo nó: `market_researcher_node`, que usa a ferramenta `search_market_price`.

- [ ] **Construção do Grafo (Parte 2 - Estrutura e Roteamento):** - [ ] Em `supply_chain_graph.py`, instanciar `StateGraph`. - [ ] Adicionar os nós criados (`demand_analyst`, `market_researcher`). - [ ] Definir `demand_analyst` como o ponto de entrada (`entry_point`). - [ ] Adicionar uma aresta condicional (`conditional_edge`): - Se o `demand_analyst` indicar que a compra é necessária, vá para `market_researcher`. - Caso contrário, vá para o fim (`END`). - [ ] Adicionar uma aresta do `market_researcher` para o fim (`END`) por enquanto. - [ ] Compilar o grafo (`workflow.compile()`).

- [ ] **Integração com a API:** - [ ] Criar `app/services/agent_service.py` com a função `run_purchase_analysis(sku: str)` que invoca o grafo. - [ ] Criar `app/routers/agent_router.py` com o endpoint POST `/agents/execute-analysis`. - [ ] Registrar o novo router no `app/main.py`.

- [ ] **Validação:** - **Comando:**
      ```bash # Certifique-se de que os serviços estão no ar
      docker compose up --build

        # Dispare a análise para um SKU existente
        curl -X POST http://localhost:8000/agents/execute-analysis -H "Content-Type: application/json" -d '{"sku": "seu_sku_aqui"}'
        ```
      - **Resultado Esperado:**
        - Logs da API mostrando a execução dos nós do grafo.
        - Resposta JSON no terminal contendo o estado final da análise (ex: com os preços de mercado preenchidos).

- [ ] **Expansão (Passos Futuros):** - [ ] Implementar o `logistics_analyst_node` e suas ferramentas (Fase 4.5). - [ ] Implementar o `decision_maker_node` para gerar a recomendação final. - [ ] Integrar o grafo completo, atualizando as arestas para o fluxo final.
- **Status:** PENDING

## Phase 6 — Refatoração para Pipeline de ML de Produção (LightGBM)

- [ ] **Configuração do Ambiente:** - [ ] Adicionar `lightgbm` e `scikit-learn` ao `requirements.txt`. - [ ] Criar um novo script `scripts/generate_lgbm_training_data.py` para gerar dados fictícios mais realistas (com tendências e sazonalidades distintas por categoria de produto).

- [ ] **Refatoração do Módulo de Treinamento (`app/ml/training.py`):** - [ ] Remover as funções antigas do Prophet (`train_model`, `_prepare_history_dataframe`, etc.). - [ ] Criar a função `_create_feature_rich_dataframe()` para realizar a engenharia de características (lags, janelas móveis, calendário, `produto_id` categórico). - [ ] Implementar a função principal `train_global_lgbm_model()`: - [ ] Chama a função de criação de features. - [ ] Divide os dados em treino e validação (temporal split). - [ ] Treina um `LGBMRegressor` com `early_stopping`. - [ ] Salva o modelo treinado como `/models/global_lgbm.pkl`. - [ ] Salva as métricas (ex: RMSE no conjunto de validação) na tabela `ModeloGlobal`.

- [ ] **Implementação da Função de Previsão:** - [ ] Em `app/ml/training.py`, criar a função `predict_prices(skus: list[str], horizon_days: int)`. - [ ] A função deve carregar o modelo global, construir o DataFrame de features para as datas futuras para os SKUs solicitados e retornar as previsões.

- [ ] **Atualização da Integração (API e Tarefas):** - [ ] Atualizar a tarefa Celery `retrain_all_products_task` em `app/tasks/ml_tasks.py` para chamar `train_global_lgbm_model`. - [ ] Remover a tarefa `retrain_model_task` (agora é um modelo único). - [ ] Atualizar o router `app/routers/ml_router.py` para ter apenas um endpoint de retreino global. - [ ] Criar um novo endpoint, talvez em `ml_router.py`, para `GET /ml/predict?sku=...` que utilize a função `predict_prices`.

- [ ] **Validação:** - **Comandos:**
      ```bash # 1. Gerar os novos dados de treino
      docker compose exec api python scripts/generate_lgbm_training_data.py

        # 2. Treinar o novo modelo global
        docker compose exec api python scripts/train_global_model.py

        # 3. Testar o endpoint de previsão
        curl -X GET "http://localhost:8000/ml/predict?sku=SKU123&horizon=7"
        ```
      - **Resultado Esperado:**
        - O script de treino executa sem erros e salva o artefato do modelo.
        - O endpoint da API retorna uma previsão JSON para os próximos 7 dias para o SKU solicitado.

- **Status:** PENDING
