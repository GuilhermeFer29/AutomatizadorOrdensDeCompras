FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instala apenas dependências essenciais
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Instala dependências Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -r {} + \
    && find /usr/local/lib/python3.11 -type f -name '*.pyc' -delete

# Copia apenas código (NÃO copia data - será montado como volume)
COPY app ./app
COPY scripts ./scripts

# Cria diretórios vazios que serão montados
RUN mkdir -p /app/data /app/models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
