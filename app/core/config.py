"""
Configuração Central da Aplicação - Pydantic Settings.

ARQUITETURA:
============
Este módulo usa pydantic-settings para carregar configurações
de variáveis de ambiente com validação de tipos.

HIERARQUIA DE PRIORIDADE:
1. Variáveis de ambiente (maior prioridade)
2. Arquivo .env (se existir)
3. Valores default do modelo

REFERÊNCIAS:
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- 12-Factor App Config: https://12factor.net/config
- FastAPI Settings: https://fastapi.tiangolo.com/advanced/settings/

SEGURANÇA:
- Secrets são carregados de env vars (nunca hardcoded)
- URLs são construídas dinamicamente (Docker-aware)
- Validação de tipos em runtime

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# ============================================================================
# PATHS
# ============================================================================

# Raiz do projeto (onde está o pyproject.toml ou requirements.txt)
ROOT_DIR = Path(__file__).resolve().parents[2]


# ============================================================================
# ENVIRONMENT ENUM
# ============================================================================

Environment = Literal["development", "staging", "production", "test"]


# ============================================================================
# DATABASE SETTINGS
# ============================================================================

class DatabaseSettings(BaseSettings):
    """Configurações do banco de dados MySQL/MariaDB."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",  # ex: DB_HOST, DB_USER
        extra="ignore",
    )

    # Conexão
    HOST: str = Field(default="localhost", description="Host do banco de dados")
    PORT: int = Field(default=3306, description="Porta do MySQL")
    USER: str = Field(default="root", description="Usuário do banco")
    PASSWORD: SecretStr = Field(default=SecretStr(""), description="Senha do banco")
    NAME: str = Field(default="pmi_automation", description="Nome do database")

    # Pool de conexões
    POOL_SIZE: int = Field(default=10, ge=1, le=100)
    POOL_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    POOL_RECYCLE: int = Field(default=1800, description="Segundos para reciclar conexão")
    POOL_PRE_PING: bool = Field(default=True, description="Verificar conexão antes de usar")

    # Echo SQL (debug)
    ECHO: bool = Field(default=False, description="Log SQL queries")

    @computed_field
    @property
    def SYNC_URL(self) -> str:
        """URL síncrona para SQLAlchemy (pymysql)."""
        password = self.PASSWORD.get_secret_value()
        return f"mysql+pymysql://{self.USER}:{password}@{self.HOST}:{self.PORT}/{self.NAME}"

    @computed_field
    @property
    def ASYNC_URL(self) -> str:
        """URL assíncrona para SQLAlchemy (aiomysql)."""
        password = self.PASSWORD.get_secret_value()
        return f"mysql+aiomysql://{self.USER}:{password}@{self.HOST}:{self.PORT}/{self.NAME}"

    @computed_field
    @property
    def TEST_URL(self) -> str:
        """URL para banco de testes."""
        password = self.PASSWORD.get_secret_value()
        return f"mysql+pymysql://{self.USER}:{password}@{self.HOST}:{self.PORT}/{self.NAME}_test"


# ============================================================================
# REDIS SETTINGS
# ============================================================================

class RedisSettings(BaseSettings):
    """Configurações do Redis (Cache e Result Backend)."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=6379)
    DB: int = Field(default=0, ge=0, le=15)
    PASSWORD: SecretStr | None = Field(default=None)

    # Timeouts
    SOCKET_TIMEOUT: float = Field(default=5.0)
    CONNECT_TIMEOUT: float = Field(default=10.0)

    # Cache defaults
    CACHE_TTL: int = Field(default=3600, description="TTL padrão em segundos")

    @computed_field
    @property
    def URL(self) -> str:
        """URL de conexão Redis."""
        if self.PASSWORD:
            pw = self.PASSWORD.get_secret_value()
            return f"redis://:{pw}@{self.HOST}:{self.PORT}/{self.DB}"
        return f"redis://{self.HOST}:{self.PORT}/{self.DB}"


# ============================================================================
# RABBITMQ SETTINGS
# ============================================================================

class RabbitMQSettings(BaseSettings):
    """Configurações do RabbitMQ (Celery Broker)."""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", extra="ignore")

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=5672)
    USER: str = Field(default="guest")
    PASSWORD: SecretStr = Field(default=SecretStr("guest"))
    VHOST: str = Field(default="/")

    # Management
    MANAGEMENT_PORT: int = Field(default=15672)

    @computed_field
    @property
    def URL(self) -> str:
        """URL AMQP para Celery."""
        password = self.PASSWORD.get_secret_value()
        vhost = self.VHOST if self.VHOST != "/" else ""
        return f"amqp://{self.USER}:{password}@{self.HOST}:{self.PORT}/{vhost}"


# ============================================================================
# LLM SETTINGS
# ============================================================================

class LLMSettings(BaseSettings):
    """Configurações dos modelos LLM (Gemini/OpenAI)."""

    model_config = SettingsConfigDict(extra="ignore")

    # Google Gemini
    GOOGLE_API_KEY: SecretStr | None = Field(
        default=None,
        validation_alias="GOOGLE_API_KEY"
    )
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")
    GEMINI_TEMPERATURE: float = Field(default=0.2, ge=0.0, le=2.0)
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=8192)

    # OpenAI (alternativa/fallback)
    OPENAI_API_KEY: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY"
    )
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    # Groq (alternativa)
    GROQ_API_KEY: SecretStr | None = Field(
        default=None,
        validation_alias="GROQ_API_KEY"
    )

    @computed_field
    @property
    def PRIMARY_PROVIDER(self) -> str:
        """Determina o provider primário baseado nas chaves disponíveis."""
        if self.GOOGLE_API_KEY:
            return "gemini"
        if self.OPENAI_API_KEY:
            return "openai"
        if self.GROQ_API_KEY:
            return "groq"
        return "none"


# ============================================================================
# CHROMADB SETTINGS
# ============================================================================

class ChromaDBSettings(BaseSettings):
    """Configurações do ChromaDB (Vector Store para RAG)."""

    model_config = SettingsConfigDict(env_prefix="CHROMA_", extra="ignore")

    HOST: str = Field(default="localhost")
    PORT: int = Field(default=8000)
    COLLECTION_NAME: str = Field(default="products_collection")
    PERSIST_DIR: Path = Field(default=ROOT_DIR / "data" / "chroma")

    # HTTP vs Persistent Client
    USE_HTTP_CLIENT: bool = Field(default=False)

    @computed_field
    @property
    def URL(self) -> str:
        """URL do servidor ChromaDB (se HTTP client)."""
        return f"http://{self.HOST}:{self.PORT}"


# ============================================================================
# SECURITY SETTINGS
# ============================================================================

class SecuritySettings(BaseSettings):
    """Configurações de segurança e autenticação."""

    model_config = SettingsConfigDict(extra="ignore")

    # JWT
    SECRET_KEY: SecretStr = Field(
        description="Chave secreta para JWT. OBRIGATÓRIA via env var."
    )

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: Any) -> str:
        """Garante que SECRET_KEY é fornecida e segura."""
        import os as _os
        import secrets as _secrets
        if not v or v == "dev-secret-key-change-in-production":
            env = _os.getenv("ENVIRONMENT", "development")
            if env in ("production", "staging"):
                raise ValueError(
                    "SECRET_KEY é obrigatória em produção/staging. "
                    "Gere com: python -c 'import secrets; print(secrets.token_hex(32))'"
                )
            # Dev/test: gera chave efêmera com warning
            import logging as _log
            _log.getLogger(__name__).warning(
                "SECRET_KEY não definida. Gerando chave efêmera (dev only)."
            )
            return _secrets.token_hex(32)
        if isinstance(v, str) and len(v) < 32:
            raise ValueError("SECRET_KEY deve ter pelo menos 32 caracteres.")
        return v
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Origens permitidas para CORS"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Converte string separada por vírgula em lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# ============================================================================
# ML SETTINGS
# ============================================================================

class MLSettings(BaseSettings):
    """Configurações de Machine Learning."""

    model_config = SettingsConfigDict(env_prefix="ML_", extra="ignore")

    # Diretório de modelos
    MODELS_DIR: Path = Field(default=ROOT_DIR / "models")

    # Treinamento
    DEFAULT_EPOCHS: int = Field(default=100)
    BATCH_SIZE: int = Field(default=32)
    VALIDATION_SPLIT: float = Field(default=0.2)

    # Forecast
    DEFAULT_HORIZON_DAYS: int = Field(default=14)
    MIN_TRAINING_SAMPLES: int = Field(default=30)

    # Optuna
    OPTUNA_N_TRIALS: int = Field(default=30)
    OPTUNA_TIMEOUT: int = Field(default=600)  # segundos


# ============================================================================
# APP SETTINGS (Master)
# ============================================================================

class Settings(BaseSettings):
    """
    Configurações Master da Aplicação.

    Agrega todas as sub-configurações em um objeto único.

    Uso:
        from app.core.config import get_settings
        settings = get_settings()

        # Acessa configs
        db_url = settings.database.ASYNC_URL
        redis_url = settings.redis.URL
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Ambiente
    ENVIRONMENT: Environment = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    # API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_PREFIX: str = Field(default="/api/v1")
    API_TITLE: str = Field(default="PMI Automation API")
    API_VERSION: str = Field(default="2.0.0")

    # Workers
    API_WORKERS: int = Field(default=4, ge=1)

    # Paths
    ROOT_DIR: Path = ROOT_DIR

    # Sub-configurações (lazy load)
    _database: DatabaseSettings | None = None
    _redis: RedisSettings | None = None
    _rabbitmq: RabbitMQSettings | None = None
    _llm: LLMSettings | None = None
    _chroma: ChromaDBSettings | None = None
    _security: SecuritySettings | None = None
    _ml: MLSettings | None = None

    @property
    def database(self) -> DatabaseSettings:
        """Retorna configurações do banco de dados."""
        if self._database is None:
            self._database = DatabaseSettings()
        return self._database

    @property
    def redis(self) -> RedisSettings:
        """Retorna configurações do Redis."""
        if self._redis is None:
            self._redis = RedisSettings()
        return self._redis

    @property
    def rabbitmq(self) -> RabbitMQSettings:
        """Retorna configurações do RabbitMQ."""
        if self._rabbitmq is None:
            self._rabbitmq = RabbitMQSettings()
        return self._rabbitmq

    @property
    def llm(self) -> LLMSettings:
        """Retorna configurações de LLM."""
        if self._llm is None:
            self._llm = LLMSettings()
        return self._llm

    @property
    def chroma(self) -> ChromaDBSettings:
        """Retorna configurações do ChromaDB."""
        if self._chroma is None:
            self._chroma = ChromaDBSettings()
        return self._chroma

    @property
    def security(self) -> SecuritySettings:
        """Retorna configurações de segurança."""
        if self._security is None:
            self._security = SecuritySettings()
        return self._security

    @property
    def ml(self) -> MLSettings:
        """Retorna configurações de ML."""
        if self._ml is None:
            self._ml = MLSettings()
        return self._ml

    @computed_field
    @property
    def is_production(self) -> bool:
        """Verifica se está em produção."""
        return self.ENVIRONMENT == "production"

    @computed_field
    @property
    def is_testing(self) -> bool:
        """Verifica se está em modo de teste."""
        return self.ENVIRONMENT == "test"

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        """Valida configurações críticas em produção."""
        if self.ENVIRONMENT == "production":
            # Em produção, DEBUG deve ser False
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")

            # Secret key não pode ser o default
            secret = self.security.SECRET_KEY.get_secret_value()
            if "dev-secret" in secret.lower() or secret == "CHANGE_ME_GENERATE_A_SECURE_KEY":
                raise ValueError("SECRET_KEY must be changed in production")

            # CORS não pode ser wildcard em produção
            if self.security.CORS_ORIGINS == ["*"]:
                raise ValueError("CORS_ORIGINS cannot be ['*'] in production")

            # Database não pode usar credenciais padrão
            db_pass = self.database.PASSWORD.get_secret_value()
            if self.database.USER == "root" and not db_pass:
                raise ValueError("Database must not use root with empty password in production")

            # RabbitMQ não pode usar guest:guest
            rabbit_user = self.rabbitmq.USER
            rabbit_pass = self.rabbitmq.PASSWORD.get_secret_value()
            if rabbit_user == "guest" and rabbit_pass == "guest":
                raise ValueError("RabbitMQ must not use guest:guest in production")

            # ALLOW_DEFAULT_DB deve ser False em produção
            import os
            if os.getenv("ALLOW_DEFAULT_DB", "false").lower() == "true":
                raise ValueError("ALLOW_DEFAULT_DB must be False in production")

        return self


# ============================================================================
# SINGLETON GETTER
# ============================================================================

@lru_cache
def get_settings() -> Settings:
    """
    Retorna instância singleton das configurações.

    Usa lru_cache para garantir que as settings são carregadas
    apenas uma vez durante o ciclo de vida da aplicação.

    Uso:
        from app.core.config import get_settings
        settings = get_settings()

        print(settings.database.ASYNC_URL)
        print(settings.redis.URL)
    """
    return Settings()


# ============================================================================
# COMPATIBILITY LAYER (migração gradual)
# ============================================================================

# Exposição de valores para compatibilidade com código legado
# DEPRECATED: Use get_settings() diretamente

def _get_legacy_db_url() -> str:
    """DEPRECATED: Use get_settings().database.SYNC_URL"""
    return get_settings().database.SYNC_URL

def _get_legacy_redis_url() -> str:
    """DEPRECATED: Use get_settings().redis.URL"""
    return get_settings().redis.URL

# Mantém constantes legadas para compatibilidade
DEFAULT_HORIZON_DAYS = 14  # DEPRECATED: Use get_settings().ml.DEFAULT_HORIZON_DAYS


# ============================================================================
# DOCKER AWARENESS
# ============================================================================

def is_running_in_docker() -> bool:
    """
    Detecta se está rodando dentro de container Docker.

    Útil para ajustar URLs automaticamente.
    """
    # Verifica se existe o arquivo /.dockerenv
    if os.path.exists("/.dockerenv"):
        return True

    # Verifica se cgroup indica container
    try:
        with open("/proc/1/cgroup") as f:
            return "docker" in f.read()
    except Exception:  # noqa: S110
        pass

    # Verifica variável de ambiente (pode ser setada no Dockerfile)
    return os.getenv("RUNNING_IN_DOCKER", "").lower() == "true"


def get_service_url(service_name: str, port: int, use_docker_dns: bool = None) -> str:
    """
    Retorna URL de um serviço considerando ambiente Docker.

    Args:
        service_name: Nome do serviço (ex: "db", "redis", "rabbitmq")
        port: Porta do serviço
        use_docker_dns: Se None, detecta automaticamente

    Returns:
        URL do serviço (localhost ou nome do container)

    Exemplo:
        >>> get_service_url("db", 3306)
        "db:3306"  # se em Docker
        "localhost:3306"  # se local
    """
    if use_docker_dns is None:
        use_docker_dns = is_running_in_docker()

    host = service_name if use_docker_dns else "localhost"
    return f"{host}:{port}"
