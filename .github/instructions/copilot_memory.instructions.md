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
phase: 4
status: "PENDING"

## Phase Checklist
0: PASS
1: PASS
2: PASS
3: PENDING
4: PASS
4.5: PENDING
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
- [x] Criar `app/models/models.py` com modelos SQLModel:
      - Produto
      - VendasHistoricas
      - PrecosHistoricos
      - ModeloPredicao
- [x] Implementar `create_db_and_tables()` no `main.py`
- [x] Validar conexão e criação de tabelas:
      command: |
        docker compose exec api python -m compileall app
        docker compose exec db mysql -u app_user -papp_password -e "SHOW TABLES IN app_db;"
      expected_result:
        - CompileAll sem erros
        - Tabelas `produtos`, `vendas_historicas`, `precos_historicos`, `modelos_predicao` presentes
- Status: PASS

---
## Phase 3 — MLOps + Dashboards (retrain com dados do Scraping)
- [ ] Criar `scripts/seed_database.py` (opcional: popular DB inicial com CSV histórico, mas usar dados de `PrecosHistoricos` como fonte principal).
- [ ] Criar `app/ml/training.py`:
      - Função `train_prophet_model(produto_id: int) -> str`
      - Lê dados de preços de `PrecosHistoricos` para o produto.
      - Treina modelo Prophet.
      - Salva modelo (`/models/{produto_id}.pkl`) e relatório PDF (`/reports/{produto_id}.pdf`).
- [ ] Criar `app/services/email_service.py`:
      - Função `send_training_report(to_email: str, produto_id: int, pdf_path: str) -> None`
      - Envia e-mail corporativo com PDF anexo e corpo estruturado.
- [ ] Criar `app/tasks/ml_tasks.py`:
      - Tarefa Celery `retrain_model_task(produto_id: int)` que:
        1. Executa `train_prophet_model`.
        2. Gera relatório PDF.
        3. Chama `send_training_report`.
- [ ] Criar rota `/vendas/retrain/{produto_id}`:
      - Dispara retraining para produto específico.
- [ ] Criar dashboard simples (Streamlit ou FastAPI + template frontend):
      - Página `/dashboard`:
        - Exibe gráfico histórico de preços (dados de `PrecosHistoricos`).
        - Exibe previsão do Prophet (curva futura).
        - Exibe métricas (MSE/RMSE).
- [ ] Validação:
    command: |
      docker-compose up --build
      docker-compose exec api celery -A app.core.celery_app worker --loglevel=info
      curl -X POST http://localhost:8000/vendas/retrain/1
    expected_result:
      - Worker processa tarefa `retrain_model_task`
      - Modelo salvo em `/models/`
      - Relatório PDF gerado em `/reports/`
      - E-mail enviado com PDF
      - Dashboard acessível em `/dashboard` mostrando histórico + previsão
- Status: PENDING

---

## Phase 4 — Scraping com ScraperAPI (Mercado Livre)
- [x] Criar `app/scraping/scrapers.py`:
      - Função `scrape_mercadolivre(produto_nome: str) -> Optional[float]`
      - Usa **ScraperAPI** (`http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={target_url}`)
      - Faz parsing com BeautifulSoup4.
      - Implementa retry com `tenacity` (backoff exponencial) e timeout.
      - Retorna preço como `float` ou `None`.
- [x] Criar `app/services/scraping_service.py`:
      - Função `scrape_and_save_price(produto_id: int) -> None`
      - Busca nome do produto no DB.
      - Chama `scrape_mercadolivre`.
      - Persiste preço em `PrecosHistoricos`.
- [x] Criar `app/tasks/scraping_tasks.py`:
      - Tarefa Celery `scrape_product(produto_id: int)`
      - Tarefa Celery `scrape_all_products()`
      - Ambas chamam `scraping_service`.
- [x] Atualizar `app/core/celery_app.py`:
      - Configurar `beat_schedule` com `crontab(hour="*/8")` para rodar `scrape_all_products` a cada 8h.
- [x] Atualizar `docker-compose.yml`:
      - Adicionar serviço `beat` rodando Celery Beat.
- [x] Adicionar variável no `.env`:
      - `SCRAPERAPI_KEY=...`
- [x] Validação:
    command: |
      docker-compose up --build
      docker-compose exec api celery -A app.core.celery_app worker --loglevel=info
      docker-compose exec api celery -A app.core.celery_app beat --loglevel=info
    expected_result:
      - Worker executa `scrape_all_products` automaticamente a cada 8h
      - Logs mostram produtos sendo raspados do Mercado Livre
      - Novos preços aparecem na tabela `PrecosHistoricos`
            result:
                  - PASS — Serviços `api`, `worker` e `beat` iniciados via `docker compose` (contornando erro gRPC build)
                  - Scraping validado manualmente (`scrape_mercadolivre` e `scrape_and_save_price`) com registros persistidos
                  - Logs do worker confirmam registro das tarefas `app.tasks.scraping.*`
- Status: PASS


---

## Phase 4.5 — Integração com APIs Públicas de Localização e Fornecedores
- [ ] Criar `app/services/cep_service.py`:
      - Função `get_address_from_cep(cep: str) -> Dict[str, str]` usando **ViaCEP** (gratuito, sem API key).
- [ ] Criar `app/services/geolocation_service.py`:
      - Função `get_coordinates_from_address(address: str) -> Tuple[float, float]` usando **Nominatim (OpenStreetMap)**.
      - Função `calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float` (fórmula de Haversine).
- [ ] Enriquecer `Fornecedor` no DB com:
      - CEP
      - Latitude/Longitude
- [ ] Criar lógica no serviço de pedidos:
      - Ao gerar ordem de compra, comparar fornecedores:
        - Pelo preço
        - Pelo prazo
        - Pela **proximidade geográfica** (distância).
      - Regra: em caso de **urgência**, priorizar fornecedor mais próximo.
- [ ] Criar endpoint `/fornecedores/enriquecer` para atualizar fornecedores com dados de CEP/geo.
- [ ] Observações:
      - Esses dados poderão ser usados no futuro:
        - Como **feature no modelo preditivo** (prazo de entrega estimado considerando distância).
        - Como **contexto no CrewAI** para análise multi-agente.
- [ ] Validação:
    - Seed inicial de fornecedores com CEPs.
    - Rodar enriquecimento (`/fornecedores/enriquecer`).
    - Gerar pedido com urgência → sistema deve escolher fornecedor mais próximo.
    - Logs devem mostrar cálculo de distância e fornecedor selecionado.
- Status: PENDING


---
## Phase 5 — CrewAI Agents + Deploy final
- [ ] Criar `app/agents/tools.py` (ferramentas que chamam API interna)
- [ ] Criar `app/agents/supply_chain_crew.py` (definição dos agentes e fluxo)
- [ ] Criar `app/services/crew_service.py` (função que monta e executa Crew)
- [ ] Ajustar `docker-compose.yml` para rodar `api`, `worker`, `beat`, `db`, `broker`
- [ ] Instruções de deploy (Render, Docker Swarm ou K8s)
- [ ] Validação: endpoint `/crew/execute-analysis` retorna execução real do Crew
- Status: PENDING
