FROM nvidia/cuda:13.0.1-cudnn-devel-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instala apenas o necessário: Python 3.11 + pip
# A imagem base já vem com: CUDA 12.1, build-essential, libgomp1, etc
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-dev \
        python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# Instala dependências Python (incluindo LightGBM com CUDA)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

RUN pip uninstall -y lightgbm

RUN git clone --recursive https://github.com/microsoft/LightGBM /tmp/lightgbm && \
    cd /tmp/lightgbm && \
    cmake -B build -S . -DUSE_CUDA=ON && \
    cmake --build build -j4 && \
    cd python-package && \
    pip install . && \
    rm -rf /tmp/lightgbm
    
# Copia código
COPY app ./app
COPY scripts ./scripts

# Cria diretórios
RUN mkdir -p /app/data /app/models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
