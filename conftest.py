"""
Root conftest.py — seta variáveis de ambiente para testes.

Todas as fixtures reais estão em tests/conftest.py.
"""

import os

# Env vars de teste DEVEM ser setadas antes de qualquer import da app
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ALLOW_DEFAULT_DB", "false")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("PROMETHEUS_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e-tests-only-123456")
os.environ.setdefault("CACHE_REDIS_URL", "")
