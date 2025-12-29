"""
Configuração do Pytest para testes do Backend.

Fornece fixtures para database, client HTTP e dados de teste.
"""

import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.database import get_session


# =====================================================
# DATABASE DE TESTE
# =====================================================

@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Cria uma sessão de banco de dados em memória para testes."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Cria um cliente de teste com sessão de banco mockada."""
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# =====================================================
# FIXTURES DE DADOS
# =====================================================

@pytest.fixture
def sample_product_data():
    """Dados de produto para testes."""
    return {
        "sku": "TEST001",
        "name": "Produto de Teste",
        "price": 99.99,
        "stock": 100,
    }


@pytest.fixture
def sample_order_data():
    """Dados de ordem para testes."""
    return {
        "product": "Produto de Teste",
        "quantity": 10,
        "value": 999.90,
        "origin": "Manual",
    }


@pytest.fixture
def sample_user_data():
    """Dados de usuário para testes."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def auth_headers(client: TestClient, sample_user_data: dict):
    """Headers com token de autenticação."""
    # Registrar usuário
    client.post("/auth/register", json=sample_user_data)
    
    # Login
    response = client.post(
        "/auth/login",
        data={
            "username": sample_user_data["email"],
            "password": sample_user_data["password"],
        },
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    return {}


# =====================================================
# CONFIGURAÇÕES ASSÍNCRONAS
# =====================================================

@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes assíncronos."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
