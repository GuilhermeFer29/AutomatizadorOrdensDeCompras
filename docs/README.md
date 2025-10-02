# Plataforma Preditiva — Documentação das Fases 1 a 4

## Visão Geral
A plataforma automatiza o ciclo de compras para pequenas e médias indústrias. Ela coleta dados de mercado, mantém históricos de preços, treina modelos Prophet para previsão de demanda e expõe esses resultados via API e dashboard. A infraestrutura é empacotada com Docker Compose, processamentos assíncronos via Celery/Redis e persistência relacional com SQLModel sobre MySQL.

Este documento consolida tudo que foi construído da **Fase 1 até a Fase 4**, incluindo subfases 3.1 e 3.5. Cada seção detalha objetivos, componentes de código, fluxos operacionais, variáveis importantes e comandos de validação executados durante a implementação.

## Arquitetura de Alto Nível
- **API FastAPI** (`app/main.py`) expõe rotas de tarefas, vendas (retrain), scraping, healthcheck e dashboard.
- **Celery + Redis** (`app/core/celery_app.py`) orquestram tarefas de retraining, scraping e utilidades.
- **MySQL** (`app/core/database.py`) armazena catálogos, históricos de preços, modelos treinados e metadados globais.
- **MLOps** (`app/ml/training.py`) concentra funções de preparo de dados, treino Prophet, consolidação de relatórios e artefatos.
- **Scraping** (`app/scraping`) consulta preços do Mercado Livre via ScraperAPI e persiste no banco.
- **Dashboard** (`app/routers/dashboard_router.py`) renderiza HTML com Chart.js para acompanhar históricos, previsões e métricas globais.
- **Scripts utilitários** (`scripts/`) populam produtos, geram históricos sintéticos, treinam modelos e auxiliam em cargas de dados.

### Serviços Docker
`docker-compose.yml` define os contêineres:
- **api**: Uvicorn servindo a API, com volumes read-only montando `app/`, `scripts/`, `data/` e volumes nomeados para modelos e relatórios.
- **worker**: executa `celery worker` consumindo tarefas da aplicação.
- **beat**: dispara cron jobs (`scrape_all_products` a cada 8h).
- **db**: MySQL 8 com volume `postgres_data` (compatível com planos anteriores) e healthcheck.
- **broker**: Redis 7 com persistência append-only e healthcheck.

## Fase 1 — API Base, Celery e Docker
### Objetivos
- Provisionar infraestrutura Docker.
- Publicar API FastAPI básica com rotas de tasks.
- Configurar Celery + Redis para execução assíncrona.

### Componentes Principais
- **`docker-compose.yml`**: Estrutura os serviços, dependências e volumes. Define healthchecks e comandos padrão para API e workers.
- **`app/main.py`**: Cria a aplicação FastAPI, registra middlewares CORS, inclui rotas (`tasks`, `sales`, `ml`, `dashboard`), executa `create_db_and_tables()` no startup e oferece `/health` para probes.
- **`app/core/celery_app.py`**: Função `create_celery_app()` lê `REDIS_URL`/`CELERY_RESULT_BACKEND`, define filas, expirações de resultado e agenda `scrape_all_products` a cada 8 horas via `celery beat`.
- **`app/tasks/debug_tasks.py`**: Tarefa `long_running_task` usada como smoke test com logs estruturados usando `structlog`.
- **`app/services/task_service.py`**: Camada de serviço que expõe funções `trigger_*` para enfileirar tasks e `get_task_status` para consolidar resultados/parciais via `AsyncResult`.
- **`app/routers/tasks_router.py`**: Rotas `/tasks/test`, `/tasks/scrape/all` e `/tasks/{task_id}` que consomem o serviço e retornam modelos Pydantic (`TaskResponse`, `TaskStatusResponse`).

### Fluxo Operacional
1. Cliente chama `/tasks/test` → `trigger_long_running_task` enfileira `long_running_task` → worker loga início/fim.
2. Qualquer task pode ser auditada via `/tasks/{task_id}` com o payload estruturado.
3. `celery beat` dispara periodicamente `scrape_all_products` sem intervenção manual.

### Validação Executada
```bash
docker compose up --build
docker compose exec api celery -A app.core.celery_app.celery_app worker --loglevel=info
curl -X POST http://localhost:8000/tasks/test
```
Logs esperados: entrada `Task long_running_task[...] succeeded` no worker.

## Fase 2 — Banco de Dados e Models
### Objetivos
- Configurar engine SQLModel conectando ao MySQL via variáveis `.env`.
- Modelar entidades principais: produtos, vendas, históricos de preço, modelos de previsão.
- Garantir criação de tabelas no startup da API.

### Componentes Principais
- **`app/core/database.py`**:
  - `_get_database_url()` lê `DATABASE_URL` com fallback `mysql+mysqlconnector://app_user:app_password@db:3306/app_db`.
  - `create_engine_instance()` ativa `pool_pre_ping` para lidar com conexões ociosas.
  - `create_db_and_tables()` implementa retry exponencial para aguardar MySQL e cria todas as tabelas.
  - `get_session()` fornece generator compatível com dependências FastAPI.
- **`app/models/models.py`**: Define as tabelas via SQLModel.
  - `Produto`: campos de estoque, categoria, timestamps, relacionamentos com vendas/preços/modelos.
  - `VendasHistoricas`: dados de vendas com receita agregada.
  - `PrecosHistoricos`: preços (reais ou sintéticos), fornecedor, moeda, timestamp e flag `is_synthetic`.
  - `ModeloPredicao`: metadados de modelos Prophet por produto com métricas JSON, caminho do arquivo e data de treino.
  - `ModeloGlobal`: (Fase 3.5) metadados de modelo agregado com holdout, caminhos de artefatos e métricas.

### Rotina de Inicialização
`app/main.py` executa `create_db_and_tables()` no evento `startup`, garantindo que a API só opere após as tabelas existirem.

### Validação Executada
```bash
python -m compileall app
docker compose exec db mysql -u app_user -papp_password -e "SHOW TABLES IN app_db;"
```
Tabelas esperadas: `produtos`, `vendas_historicas`, `precos_historicos`, `modelos_predicao` e `modelos_globais` (após fase 3.5).

## Fase 3 — MLOps, Dashboard e Relatórios
### Objetivos
- Treinar modelos Prophet por produto e catálogo global.
- Gerar relatórios PDF com métricas e gráficos.
- Acionar treinamentos via Celery e enviar e-mails corporativos.
- Disponibilizar dashboard web com histórico e previsões.

### Núcleo de Treinamento (`app/ml/training.py`)
- **Constantes e setup**: Garante diretórios `models/` e `reports/` (montados via volumes Docker).
- **`train_model(produto_id)`**:
  - Busca produto e histórico real (`_prepare_history_dataframe`) ignorando `is_synthetic=True`.
  - Treina Prophet diário/semanal, calcula métricas MSE/RMSE, persiste modelo `.pkl` e `ModeloPredicao` no MySQL.
  - Gera PDF individual com `_generate_single_product_report()` contendo gráfico e métricas.
- **`train_all_products()`**:
  - Itera sobre todos os produtos, captura `SkippedProduct` quando há histórico insuficiente.
  - Consolida PDF do catálogo com resumo e páginas individuais.
- **`train_global_model()`** (Subfase 3.5):
  - Agrega histórico real diário de todos os produtos, aplicando interpolação e preenchimento de gaps.
  - Reserva holdout de até 30 dias (respeitando histórico mínimo), calcula métricas no conjunto de validação.
  - Salva modelo global, relatório PDF e escreve `global_metadata.json` + entrada na tabela `ModeloGlobal`.
- **`load_global_dashboard_artifacts()`**: Reabre modelo e forecast para exibição no dashboard, informando métricas, holdout e caminho do relatório.

### Geração de Relatórios
- Funções auxiliares `_create_forecast_plot`, `_generate_single_product_report`, `_generate_bulk_report`, `_generate_global_report` usam Matplotlib + ReportLab para gerar PDFs com gráficos, métricas e resumos.

### Tarefas Celery (`app/tasks/ml_tasks.py`)
- `retrain_model_task(produto_id, destinatario_email)`:
  - Executa `train_model`, captura métricas mais recentes, chama `send_training_report` e retorna payload estruturado.
  - Protegida com `autoretry_for=(Exception,)` e backoff exponencial.
- `retrain_all_products_task(destinatario_email)`:
  - Executa `train_all_products`, envia relatório consolidado e retorna listas de treinados/ignorados.

### Serviço de E-mail (`app/services/email_service.py`)
- Lê credenciais SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, etc.).
- Usa `tenacity` para retry no envio (`_dispatch_email`).
- Monta corpo com métricas do modelo consultando `ModeloPredicao`/`Produto`.

### Dashboard (`app/routers/dashboard_router.py`)
- Renderiza HTML com Chart.js e estilização moderna.
- Exibe histórico real vs sintético, forecast Prophet por produto, métricas e data do último treino.
- Integração global (Subfase 3.5): seção "+ Visão Geral do Catálogo" com métricas agregadas, holdout e link de download para `/dashboard/global/report`.
- Rota `/dashboard/global/report` devolve PDF mais recente usando `FileResponse`.

### Subfase 3.1 — Histórico Sintético
- **`scripts/generate_synthetic_history.py`**: Gera até 6 meses de preços com sazonalidade, ruído e ajustes de promoção/finais de semana, marcando registros com `is_synthetic=True`.
- `_prepare_history_dataframe` filtra `is_synthetic=False`, garantindo que modelos Prophet sejam treinados apenas em dados reais.
- Dashboard diferencia pontos reais (azul) e sintéticos (vermelho tracejado).

### Subfase 3.5 — Modelo Global
- Atualizações em `app/ml/training.py`, `app/models/models.py` e `app/routers/dashboard_router.py` acrescentam:
  - Holdout mínimo de 30 dias quando histórico permite.
  - Persistência em `ModeloGlobal` + `global_metadata.json`.
  - Exibição no dashboard com métricas globais e link de download.

### Scripts MLOps
- `scripts/train_global_model.py`: CLI que carrega `.env`, executa `train_global_model()` e imprime caminho do relatório.
- `scripts/train_all_models.py`: Gatilho em lote para treinar todos os produtos respeitando mínimo de registros reais.
- `scripts/seed_price_history.py`: Popular histórico real a partir de seeds determinísticos.

### Validações Executadas
- Compilação:
  ```bash
  python3 -m compileall app/ml/training.py app/routers/dashboard_router.py
  ```
- Treino global manual:
  ```bash
  docker compose exec api python scripts/train_global_model.py
  ```
- Geração de histórico sintético + retraining Celery:
  ```bash
  python scripts/generate_synthetic_history.py
  docker compose exec api celery -A app.core.celery_app.celery_app worker --loglevel=info
  curl -X POST http://localhost:8000/vendas/retrain/1
  ```

## Fase 4 — Scraping com ScraperAPI
### Objetivos
- Coletar preços de produtos direto do Mercado Livre.
- Persistir novos registros em `PrecosHistoricos`.
- Automatizar execuções via Celery Beat.

### Componentes Principais
- **`app/scraping/scrapers.py`**:
  - `scrape_mercadolivre(produto_nome)` monta URL, chama ScraperAPI e usa BeautifulSoup para extrair preços (regex + seletores).
  - `ScraperConfig` define tentativas, timeout e backoff exponencial usando `tenacity`.
  - Trata exceções com logs específicos (`ScraperAPIConfigurationError`, `ScraperAPIRequestError`).
- **`app/services/scraping_service.py`**:
  - `scrape_and_save_price(produto_id)` valida produto e termo de busca, chama `scrape_mercadolivre`, converte preço em `Decimal`, insere registro com timestamp UTC e retorna `ScrapingOutcome`.
- **`app/tasks/scraping_tasks.py`**:
  - `scrape_product(produto_id)` para execuções unitárias (ex.: debugging).
  - `scrape_all_products()` percorre catálogo completo, captura exceções por produto sem interromper o lote e loga estatísticas.
- **Celery Beat**: configurado em `celery_app.conf.beat_schedule` para acionar `scrape_all_products` a cada 8 horas.

### Validações Executadas
```bash
docker compose up --build
docker compose exec api celery -A app.core.celery_app.celery_app worker --loglevel=info
docker compose exec api celery -A app.core.celery_app.celery_app beat --loglevel=info
```
Logs esperados: tasks de scraping registradas em `app.tasks.scraping.*` e novos registros em `PrecosHistoricos`.

## Scripts de Seed e Dados
- **`data/products_seed.csv`**: Catálogo base com 3.000 variações de produtos (nome, SKU, categoria, estoques).
- **`scripts/seed_products.py` / `scripts/seed_database.py`** (quando utilizados) podem carregar CSV no MySQL.
- **`scripts/populate_historical_prices.py`**: Alternativa de geração de histórico com tendência e sazonalidade por categoria.

## Variáveis de Ambiente Relevantes
- Banco: `DATABASE_URL`, `MYSQL_*`.
- Celery/Redis: `REDIS_URL`, `CELERY_RESULT_BACKEND`.
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_DEFAULT_RECIPIENT`, `SMTP_USE_TLS`.
- ScraperAPI: `SCRAPERAPI_KEY`, `SCRAPERAPI_TIMEOUT`, `SCRAPERAPI_MAX_ATTEMPTS`, `SCRAPERAPI_MIN_BACKOFF`, `SCRAPERAPI_MAX_BACKOFF`, `SCRAPING_CURRENCY`.
- Outros: `PYTHONPATH=/app`, `TZ` (se desejado), variáveis Docker de acesso ao MySQL.

## Observabilidade e Logs
- Toda a aplicação utiliza `structlog` para logs estruturados com chaves (`produto_id`, `metricas`, `pdf_path`, etc.), facilitando análise em ferramentas de log.
- Tarefas Celery registram início/fim e dados relevantes. Erros específicos (ScraperAPI, SMTP, histórico insuficiente) possuem códigos de log dedicados.

## Estrutura de Pastas (recorte principal)
```
app/
  core/
  models/
  ml/
  routers/
  services/
  scraping/
  tasks/
  ...
models/
reports/
data/
scripts/
docs/README.md  ← este documento
```

## Próximos Passos (Planejados para Fases Futuras)
- **Fase 4.5**: Enriquecimento de fornecedores com dados geográficos (ViaCEP + Nominatim) e lógica de seleção por proximidade.
- **Fase 5**: Integração de agentes CrewAI, ferramentas internas e estratégia de deploy (Render / Docker Swarm / K8s).

## Referências Rápidas
### Rodar Treino Individual
```bash
curl -X POST http://localhost:8000/vendas/retrain/1
```
### Rodar Treino Global
```bash
docker compose exec api python scripts/train_global_model.py
```
### Ver Dashboard
Acesse `http://localhost:8000/dashboard` após iniciar o serviço `api`.

---
Documentação compilada em 02/10/2025 cobrindo Phases 1–4 com base no estado atual do branch `master`.
