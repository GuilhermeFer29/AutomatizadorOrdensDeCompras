Roadmap Hiperdetalhado: Plataforma Preditiva para Compras (Foco em Backend Robusto)
Filosofia do Projeto: Construir a Fábrica Primeiro, Depois os Robôs
A estratégia deste roadmap é priorizar a construção de uma base de backend escalável e resiliente. Em vez de executar tarefas pesadas (ML, scraping) em tempo real, vamos criar uma "fábrica" de dados assíncrona. Esta fábrica irá coletar informações, processá-las e treinar modelos de forma independente e agendada. Somente após a fábrica estar 100% operacional, iremos conectar os "robôs" (agentes de IA) para consumir os dados e insights de alta qualidade que ela produz.

Duração Estimada: 30 dias (4 horas/dia)

Pilha de Tecnologias (Stack)
Linguagem: Python 3.11+

API Framework: FastAPI

Banco de Dados: PostgreSQL

ORM / Validação: SQLModel, Pydantic

Processamento Assíncrono:

Fila de Tarefas: Celery

Message Broker: Redis

Agendamento (Scheduler): Celery Beat

Machine Learning: Prophet, Pandas, Scikit-learn

Coleta de Dados: BeautifulSoup4, Requests

Inteligência/Agentes: CrewAI

Containerização e Orquestração: Docker, Docker Compose

Semana 1: A Base da Plataforma Assíncrona (20 horas)
Objetivo: Montar e validar a arquitetura base com FastAPI, Celery e Redis funcionando em conjunto, usando uma estrutura de projeto profissional.

Dia 1-2: Configuração do Ambiente e Estrutura do Projeto

[x] Ação: Criar o ambiente virtual (python -m venv .venv) e ativá-lo.

[x] Ação: Iniciar o repositório Git (git init) e criar um .gitignore a partir de um template para Python (ex: do gitignore.io).

[x] Ação: Instalar dependências iniciais: pip install fastapi uvicorn "sqlalchemy[psycopg2-binary]" sqlmodel celery[redis] python-dotenv.

[x] Ação: Definir a nova estrutura de pastas:

/app
├── routers/       # Endpoints da API (a camada de entrada)
├── services/      # Lógica de negócio (onde a "mágica" acontece)
├── middlewares/   # Middlewares customizados (ex: logging de requisições)
├── core/          # Configurações (Celery, DB, settings)
├── models/        # Modelos do SQLModel (representação do DB)
├── tasks/         # Tarefas do Celery (trabalho em background)
├── ml/            # Lógica e modelos de Machine Learning
├── scraping/      # Lógica e parsers de Web Scraping
└── main.py        # Ponto de entrada da API
/data              # Para datasets e modelos salvos
docker-compose.yml
Dockerfile
.env

Dia 3-5: Integração FastAPI + Celery + Redis

[ ] Ação: No docker-compose.yml, defina os serviços db (imagem: Mysql) e broker (imagem: redis:7). Configure volumes para persistência de dados do Postgres.

[ ] Ação: Em app/core/celery_app.py, configure a instância do Celery. Exemplo: celery_app = Celery("worker", broker="redis://broker:6379/0", backend="redis://broker:6379/0").

[ ] Ação: Em app/tasks/debug_tasks.py, crie uma tarefa de teste: @celery_app.task def long_running_task(a, b): time.sleep(5); return a + b.

[ ] Ação: Em app/services/task_service.py, crie uma função que dispara a tarefa: def run_test_task(): task = long_running_task.delay(5, 10); return {"task_id": task.id}.

[ ] Ação: Em app/routers/tasks_router.py, crie o endpoint que chama o serviço: @router.post("/test") def trigger_test_task(): return services.task_service.run_test_task().

[ ] Meta de Validação: Execute docker-compose up --build. Crie um terminal para o worker (docker-compose exec api celery -A app.core.celery_app worker --loglevel=info). Faça uma requisição ao endpoint /tasks/test e veja a tarefa ser processada no log do worker.

Dia 6-7: Modelagem e Conexão com o Banco de Dados

[ ] Ação: Em app/core/database.py, configure a engine de conexão do SQLAlchemy lendo a URL do DB a partir de variáveis de ambiente (.env).

[ ] Ação: Em app/models/models.py, defina as tabelas com SQLModel. Seja explícito sobre relacionamentos e tipos de dados.

Produto: id, nome, sku, estoque_atual, url_alvo_scraping. Adicione precos: List["PrecosHistoricos"] = Relationship(back_populates="produto").

VendasHistoricas: id, produto_id (com ForeignKey), quantidade, data_venda.

PrecosHistoricos: id, produto_id (com ForeignKey), preco, fonte, data_coleta. Adicione produto: "Produto" = Relationship(back_populates="precos").

ModeloPredicao: id, produto_id (com ForeignKey), path_arquivo_modelo, data_treinamento, metrica_acuracia.

[ ] Ação: Em main.py, adicione uma função create_db_and_tables() que será chamada na inicialização para criar as tabelas no banco de dados.

Semana 2: Pipeline de MLOps v1 (20 horas)
Objetivo: Criar e automatizar o pipeline de retreinamento dos modelos de Machine Learning.

Dia 8-10: Ingestão de Dados e Lógica de Treinamento

[ ] Ação: Crie um script scripts/seed_database.py. Ele deve: 1. Conectar-se ao DB. 2. Usar Pandas para ler o CSV do Kaggle. 3. Iterar no DataFrame e criar instâncias dos seus modelos SQLModel. 4. Adicionar e comitar na sessão do banco.

[ ] Ação: Crie o módulo app/ml/training.py e a função train_prophet_model(produto_id).

Passo 1 (Coleta de Dados): Crie uma função de serviço em app/services/vendas_service.py chamada get_sales_history(produto_id) que consulta o banco de dados.

Passo 2 (Preparação): Na função de treino, chame o serviço para obter os dados. Renomeie as colunas para ds (data) e y (quantidade).

Passo 3 (Treino e Serialização): Instancie (m = Prophet()), treine (m.fit(df)) e use a função model_to_json do Prophet para salvar o modelo em /data/models/modelo_{produto_id}.json.

Passo 4 (Registro): Crie um serviço ml_service.py com a função save_model_record() que salva as informações do novo modelo na tabela ModeloPredicao.

Recurso: Dataset Superstore Sales (Kaggle)

Dia 11-14: Automatizando o Retreinamento

[ ] Ação: Em app/tasks/ml_tasks.py, crie a tarefa @celery_app.task def retrain_model_task(produto_id) que chama app.ml.training.train_prophet_model(produto_id).

[ ] Ação: Em app/routers/vendas_router.py, crie o endpoint POST /vendas/upload.

Serviço: Crie app/services/vendas_service.py com a função process_sales_upload(file).

Lógica no Serviço: A função deve ler o arquivo (io.StringIO), salvá-lo no banco e retornar uma lista de produto_id únicos que foram atualizados.

Lógica no Roteador: O endpoint chama o serviço e, para cada produto_id retornado, dispara a tarefa retrain_model_task.delay(produto_id).

[ ] Ação: Crie o endpoint GET /produtos/{produto_id}/prever-demanda. Ele chamará uma função de serviço que: 1. Busca o path do modelo mais recente no DB. 2. Carrega o modelo com model_from_json. 3. Gera a previsão e retorna o resultado.

Semana 3: Pipeline de Coleta de Dados (Web Scraping) (20 horas)
Objetivo: Criar e agendar a coleta automática de preços, tornando o sistema autossuficiente em dados de mercado.

Dia 15-17: Tarefa de Scraping no Celery

[ ] Ação: Crie o módulo app/scraping/scrapers.py. Defina a função scrape_mercado_livre(url).

Detalhe: Use um header com User-Agent para simular um navegador. Use BeautifulSoup para encontrar elementos específicos (ex: soup.find('span', class_='ui-pdp-price__figure')). Adicione try/except para AttributeError (se o elemento não for encontrado) ou requests.exceptions.RequestException.

[ ] Ação: Crie um serviço scraping_service.py com a função scrape_and_save_price(produto_id).

[ ] Ação: Em app/tasks/scraping_tasks.py, crie a tarefa @celery_app.task def scrape_product_price_task(produto_id) que chama a função do serviço.

Dia 18-21: Agendamento com Celery Beat

[ ] Ação: Adicione o serviço beat ao docker-compose.yml (command: celery -A app.core.celery_app beat...).

[ ] Ação: Em app/core/celery_app.py, configure a agenda do Celery Beat.

celery_app.conf.beat_schedule = {
    'scrape-all-products-every-8-hours': {
        'task': 'app.tasks.scraping_tasks.scrape_all_products',
        'schedule': crontab(hour='*/8'),
    },
}


[ ] Ação: Crie a nova tarefa scrape_all_products que busca todos os produtos do DB e dispara scrape_product_price_task.delay(produto.id) para cada um.

Recurso: Agendamento com Celery Beat (Guia do Real Python)

Semana 4: A Camada de Inteligência e Deploy (20 horas)
Objetivo: Com a plataforma de dados robusta, conectar a camada de agentes de IA e preparar para o deploy final.

Dia 22-25: Implementando a Equipe CrewAI

[ ] Ação: Instale o CrewAI: pip install crewai.

[ ] Ação: Em app/agents/tools.py, crie as Ferramentas. Elas devem usar um cliente HTTP como httpx para chamar a API internamente (o nome do serviço no Docker Compose, ex: http://api:8000/...).

tool_get_demand_forecast(product_id: int) -> str

tool_get_best_price(product_id: int) -> str

tool_get_stock_level(product_id: int) -> str

[ ] Ação: Em app/agents/supply_chain_crew.py, defina os Agentes (Monitor, Analista) e suas Tarefas, passando as ferramentas criadas.

[ ] Ação: Em app/services/crew_service.py, crie a função run_supply_chain_analysis() que monta e inicia a Crew.

[ ] Ação: Em app/routers/crew_router.py, crie o endpoint POST /crew/execute-analysis que chama o serviço.

Dia 26-30: Dockerização Final e Deploy

[ ] Ação: Otimize o Dockerfile com multi-stage builds para reduzir o tamanho da imagem final.

[ ] Ação: Finalize o docker-compose.yml, garantindo que todos os serviços (api, worker, beat, db, redis) estejam configurados com variáveis de ambiente do arquivo .env.

[ ] Ação: Teste o ambiente completo localmente com docker-compose up. Verifique os logs de todos os serviços.

[ ] Ação: Faça o deploy no Render:

Crie um "Blueprint" a partir do seu repositório Git.

O Render irá detectar e configurar os serviços do docker-compose.yml.

Na interface do Render, vá em "Environment" e adicione as variáveis de ambiente do seu arquivo .env como segredos.

[ ] Ação Pós-Deploy: Use o shell do Render para rodar o script seed_database.py e popular o banco de dados em produção. Verifique os logs para garantir que o Celery Beat está agendando as tarefas corretamente.