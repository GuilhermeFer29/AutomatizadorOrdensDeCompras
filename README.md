# Automação Inteligente de Ordens de Compra

Este projeto implementa um sistema end-to-end para a automação inteligente de ordens de compra, utilizando um modelo de Machine Learning para prever a flutuação de preços de produtos e otimizar o momento da aquisição.

## Core Features

- **Previsão de Preços**: Utiliza um modelo **LightGBM** global para prever a tendência de preços de todo o catálogo de produtos.
- **Dashboard Interativo**: Uma interface web construída com **FastAPI** que exibe o histórico de preços, as previsões do modelo e métricas de performance.
- **Geração de Dados Sintéticos**: Inclui um script robusto para popular o banco de dados com produtos, histórico de vendas e flutuações de preços, permitindo o desenvolvimento e teste do sistema sem dados reais.
- **Arquitetura Escalável**: Baseado em contêineres **Docker** e uma arquitetura de microsserviços com fila de tarefas (**Celery** e **Redis**), garantindo escalabilidade e resiliência.
- **Ambiente de Desenvolvimento Automatizado**: Com um único comando, é possível configurar todo o ambiente, popular o banco de dados e treinar o modelo de previsão.

---

## Arquitetura do Sistema


- **API (FastAPI)**: O coração da aplicação. Serve o dashboard, processa as requisições do usuário e chama o modelo de ML para obter previsões.
- **Banco de Dados (MySQL)**: Armazena todas as informações persistentes, como produtos, histórico de preços e vendas, e metadados dos modelos treinados.
- **Modelo ML (LightGBM)**: O arquivo `.pkl` do modelo treinado. É carregado pela API para gerar previsões sob demanda.
- **Broker (Redis)**: Fila de mensagens que desacopla a API de tarefas pesadas. Futuramente, o retreinamento do modelo pode ser disparado como uma tarefa em background.
- **Worker (Celery)**: Processo que consome tarefas da fila do Redis e as executa. Atualmente configurado, mas sem tarefas implementadas.

---

## Tecnologias Utilizadas

- **Backend**: Python 3.11, FastAPI
- **Machine Learning**: LightGBM, Pandas, Scikit-learn
- **Banco de Dados**: MySQL
- **Fila de Tarefas**: Celery, Redis
- **Infraestrutura**: Docker, Docker Compose
- **ORM**: SQLModel

---

## Configuração e Instalação

Siga os passos abaixo para configurar o ambiente de desenvolvimento local.

### 1. Pré-requisitos

- **Docker** e **Docker Compose** instalados.
- **Git** para clonar o repositório.

### 2. Clone o Repositório

```bash
git clone https://github.com/GuilhermeFer29/AutomatizadorOrdensDeCompras.git
cd AutomadorOrdensDeCompras
```

### 3. Crie o Arquivo de Ambiente

Crie um arquivo chamado `.env` na raiz do projeto, copiando o conteúdo de `.env.example` (se existir) ou usando o template abaixo. Preencha com suas credenciais.

```env
# Credenciais do Banco de Dados
MYSQL_ROOT_PASSWORD=your_root_password
MYSQL_DATABASE=purchase_orders
MYSQL_USER=user
MYSQL_PASSWORD=password

# Configuração do Broker
CELERY_BROKER_URL=redis://broker:6379/0
CELERY_RESULT_BACKEND=redis://broker:6379/0
```

### 4. Construa e Inicie os Contêineres

Este comando irá construir as imagens Docker e iniciar todos os serviços em background.

```bash
docker compose up --build -d
```

### 5. Popule o Banco e Treine o Modelo

Execute o script de setup para popular o banco de dados com dados sintéticos e treinar o modelo de previsão. O modelo treinado (`.pkl`) e seus metadados (`.json`) serão salvos na pasta `models/`.

```bash
docker compose exec api python -m scripts.setup_development all
```

O argumento `all` executa tanto o *seed* do banco quanto o treinamento. Você também pode usar `seed` ou `train` separadamente.

---

## Como Usar

### Acessando o Dashboard

Após a conclusão de todos os passos de instalação, o dashboard estará disponível no seu navegador em:

**[http://localhost:8000/dashboard](http://localhost:8000/dashboard)**

O dashboard exibirá o histórico de preços de um produto e a previsão gerada pelo modelo LightGBM para os próximos 14 dias.

### Reiniciando a Aplicação

Como o modelo treinado agora é persistente graças ao volume mapeado no `docker-compose.yml`, você pode reiniciar os serviços a qualquer momento sem perder o treinamento.

```bash
# Para reiniciar todos os serviços
docker compose restart

# Para reiniciar apenas a API
docker compose restart api
```

---

## Fluxo de Dados e Machine Learning

O processo de ponta a ponta, desde a geração de dados até a previsão, segue os seguintes passos:

1.  **Geração de Dados (`scripts/setup_development.py`)**: Dados sintéticos de produtos, preços e vendas são criados e inseridos no MySQL.

2.  **Treinamento (`app/ml/training.py`)**: 
    - Os dados históricos são carregados do banco.
    - **Feature Engineering**: Novas features são criadas a partir das datas (dia da semana, mês) e de valores passados (lags, médias móveis).
    - **Divisão Temporal**: O dataset é dividido em conjuntos de treino e validação com base no tempo, para simular um cenário real.
    - **Treinamento do LightGBM**: O modelo é treinado com os dados de treino, usando o conjunto de validação para *early stopping* (parar o treino quando a performance para de melhorar).
    - **Persistência**: O modelo treinado e os metadados (como métricas de RMSE) são salvos na pasta `models/`.

3.  **Previsão (`app/routers/dashboard_router.py` -> `app/ml/training.py`)**:
    - Quando o dashboard é carregado, a API solicita uma previsão.
    - O modelo salvo em `models/global_lgbm_model.pkl` é carregado na memória.
    - Para cada produto, o histórico de preços recente é usado para criar as mesmas features do treinamento.
    - O modelo gera previsões de forma autorregressiva: a previsão de hoje é usada como um dado de entrada para prever amanhã, e assim por diante, até completar o horizonte de 14 dias.
    - As previsões são retornadas para a API e exibidas no gráfico do dashboard.
