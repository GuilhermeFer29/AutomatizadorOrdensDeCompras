"""
Configuração do Pytest para testes E2E do Backend.

Fornece fixtures robustas para:
- Database SQLite in-memory (substituindo MySQL)
- Override de TODAS as dependencies (get_session, get_tenant_session, get_current_user)
- Autenticação simulada com JWT real
- Cache desabilitado (sem Redis)
- Dados de seed para testes

Autor: Suite E2E | Data: 2026-02-07
"""

import os
import uuid

# ============================================================================
# VARIÁVEIS DE AMBIENTE (ANTES de importar a app)
# ============================================================================
os.environ["APP_ENV"] = "development"
os.environ["ALLOW_DEFAULT_DB"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PROMETHEUS_ENABLED"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-for-e2e-tests-only-123456"
os.environ["CACHE_REDIS_URL"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.database import get_session
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
)
from app.core.tenant import get_tenant_session, set_current_tenant_id
from app.models.models import (
    Agente,
    AuditoriaDecisao,
    ChatMessage,
    ChatSession,
    Fornecedor,
    OfertaProduto,
    OrdemDeCompra,
    PrecosHistoricos,
    Produto,
    Tenant,
    User,
    VendasHistoricas,
)


# ============================================================================
# DATABASE DE TESTE (SQLite in-memory)
# ============================================================================

@pytest.fixture(name="engine")
def engine_fixture():
    """Cria engine SQLite in-memory para testes."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(name="session")
def session_fixture(engine) -> Session:
    """Cria sessão de teste com rollback automático."""
    with Session(engine) as session:
        yield session


# ============================================================================
# TENANT + USER DE TESTE
# ============================================================================

@pytest.fixture(name="test_tenant")
def test_tenant_fixture(session: Session) -> Tenant:
    """Cria tenant de teste."""
    tenant = Tenant(
        nome="Empresa Teste LTDA",
        slug="empresa-teste",
        plano="pro",
        ativo=True,
        max_usuarios=10,
        max_produtos=500,
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session, test_tenant: Tenant) -> User:
    """Cria usuário owner de teste."""
    user = User(
        email="owner@empresa-teste.com",
        hashed_password=get_password_hash("TestSenha123"),
        full_name="Dono da Empresa",
        is_active=True,
        tenant_id=test_tenant.id,
        role="owner",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="test_admin_user")
def test_admin_user_fixture(session: Session, test_tenant: Tenant) -> User:
    """Cria usuário admin para testes de permissão."""
    user = User(
        email="admin@empresa-teste.com",
        hashed_password=get_password_hash("AdminSenha123"),
        full_name="Admin da Empresa",
        is_active=True,
        tenant_id=test_tenant.id,
        role="admin",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="test_viewer_user")
def test_viewer_user_fixture(session: Session, test_tenant: Tenant) -> User:
    """Cria usuário viewer (menor permissão) para testes de RBAC."""
    user = User(
        email="viewer@empresa-teste.com",
        hashed_password=get_password_hash("ViewerSenha123"),
        full_name="Viewer",
        is_active=True,
        tenant_id=test_tenant.id,
        role="viewer",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ============================================================================
# JWT TOKEN FIXTURES
# ============================================================================

@pytest.fixture(name="auth_token")
def auth_token_fixture(test_user: User, test_tenant: Tenant) -> str:
    """Gera JWT token válido para o owner."""
    return create_access_token(
        data={
            "sub": test_user.email,
            "tenant_id": str(test_tenant.id),
            "user_id": test_user.id,
            "role": test_user.role,
        }
    )


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(auth_token: str) -> dict:
    """Headers com Bearer token do owner."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(name="admin_auth_headers")
def admin_auth_headers_fixture(test_admin_user: User, test_tenant: Tenant) -> dict:
    """Headers com Bearer token do admin."""
    token = create_access_token(
        data={
            "sub": test_admin_user.email,
            "tenant_id": str(test_tenant.id),
            "user_id": test_admin_user.id,
            "role": test_admin_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="viewer_auth_headers")
def viewer_auth_headers_fixture(test_viewer_user: User, test_tenant: Tenant) -> dict:
    """Headers com Bearer token do viewer."""
    token = create_access_token(
        data={
            "sub": test_viewer_user.email,
            "tenant_id": str(test_tenant.id),
            "user_id": test_viewer_user.id,
            "role": test_viewer_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# TEST CLIENT COM DEPENDENCY OVERRIDES
# ============================================================================

@pytest.fixture(name="client")
def client_fixture(session: Session, test_user: User, test_tenant: Tenant):
    """
    TestClient com TODAS as dependencies mockadas:
    - get_session → sessão SQLite
    - get_tenant_session → mesma sessão (sem filtro real de tenant)
    - get_current_user → retorna test_user diretamente
    - FastAPICache → InMemoryBackend (sem Redis)
    """
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend

    from app.main import create_application

    # Inicializa cache em memória ANTES de criar TestClient
    FastAPICache.init(InMemoryBackend(), prefix="test-cache")

    app = create_application()

    def _override_session():
        return session

    def _override_tenant_session():
        set_current_tenant_id(test_tenant.id)
        return session

    async def _override_current_user():
        set_current_tenant_id(test_tenant.id)
        return test_user

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_tenant_session] = _override_tenant_session
    app.dependency_overrides[get_current_user] = _override_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(name="unauthenticated_client")
def unauthenticated_client_fixture(session: Session):
    """TestClient SEM autenticação (para testar rotas públicas e erros 401)."""
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend

    from app.main import create_application

    FastAPICache.init(InMemoryBackend(), prefix="test-cache")

    app = create_application()

    def _override_session():
        return session

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# FIXTURES DE DADOS PRÉ-POPULADOS
# ============================================================================

@pytest.fixture(name="sample_product")
def sample_product_fixture(session: Session, test_tenant: Tenant) -> Produto:
    """Cria um produto de teste no banco."""
    product = Produto(
        sku="SKU_001",
        nome="Parafuso Sextavado M8",
        categoria="Fixação",
        estoque_atual=150,
        estoque_minimo=50,
        tenant_id=test_tenant.id,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@pytest.fixture(name="sample_product_low_stock")
def sample_product_low_stock_fixture(session: Session, test_tenant: Tenant) -> Produto:
    """Produto com estoque abaixo do mínimo (para alertas)."""
    product = Produto(
        sku="SKU_CRITICO",
        nome="Porca Travante M6",
        categoria="Fixação",
        estoque_atual=5,
        estoque_minimo=50,
        tenant_id=test_tenant.id,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@pytest.fixture(name="sample_supplier")
def sample_supplier_fixture(session: Session, test_tenant: Tenant) -> Fornecedor:
    """Cria fornecedor de teste."""
    supplier = Fornecedor(
        nome="Distribuidora Nacional",
        cep="01310-100",
        confiabilidade=0.95,
        prazo_entrega_dias=5,
        latitude=-23.5505,
        longitude=-46.6333,
        tenant_id=test_tenant.id,
    )
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


@pytest.fixture(name="sample_offer")
def sample_offer_fixture(
    session: Session,
    sample_product: Produto,
    sample_supplier: Fornecedor,
    test_tenant: Tenant,
) -> OfertaProduto:
    """Cria oferta de teste vinculando produto a fornecedor."""
    offer = OfertaProduto(
        produto_id=sample_product.id,
        fornecedor_id=sample_supplier.id,
        preco_ofertado=14.50,
        estoque_disponivel=500,
        tenant_id=test_tenant.id,
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return offer


@pytest.fixture(name="sample_order")
def sample_order_fixture(
    session: Session,
    sample_product: Produto,
    sample_supplier: Fornecedor,
    test_tenant: Tenant,
) -> OrdemDeCompra:
    """Cria ordem de compra pendente."""
    order = OrdemDeCompra(
        produto_id=sample_product.id,
        fornecedor_id=sample_supplier.id,
        quantidade=100,
        valor=1450.00,
        status="pending",
        origem="Manual",
        tenant_id=test_tenant.id,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@pytest.fixture(name="sample_approved_order")
def sample_approved_order_fixture(
    session: Session,
    sample_product: Produto,
    sample_supplier: Fornecedor,
    test_tenant: Tenant,
) -> OrdemDeCompra:
    """Ordem já aprovada (para testar que não pode ser re-aprovada)."""
    order = OrdemDeCompra(
        produto_id=sample_product.id,
        fornecedor_id=sample_supplier.id,
        quantidade=50,
        valor=725.00,
        status="approved",
        origem="Automática",
        tenant_id=test_tenant.id,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@pytest.fixture(name="sample_price_history")
def sample_price_history_fixture(
    session: Session,
    sample_product: Produto,
    test_tenant: Tenant,
) -> list[PrecosHistoricos]:
    """Cria histórico de preços para testes de tendência."""
    from datetime import UTC, datetime, timedelta

    prices = []
    for i in range(10):
        price = PrecosHistoricos(
            produto_id=sample_product.id,
            fornecedor="Distribuidora Nacional",
            preco=14.50 + (i * 0.10),
            moeda="BRL",
            coletado_em=datetime.now(UTC) - timedelta(days=10 - i),
            tenant_id=test_tenant.id,
        )
        session.add(price)
        prices.append(price)

    session.commit()
    for p in prices:
        session.refresh(p)
    return prices


@pytest.fixture(name="sample_audit_decision")
def sample_audit_decision_fixture(
    session: Session,
    test_tenant: Tenant,
) -> AuditoriaDecisao:
    """Cria decisão de auditoria para testes."""
    decision = AuditoriaDecisao(
        agente_nome="Gerente de Compras",
        sku="SKU_001",
        acao="Análise de Compra",
        decisao="Aprovar compra de 100 unidades do fornecedor Distribuidora Nacional",
        raciocinio="Estoque abaixo do mínimo, previsão de alta demanda",
        contexto="Estoque: 45/80 | Previsão: +15% em 7 dias",
        tenant_id=test_tenant.id,
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    return decision


@pytest.fixture(name="sample_chat_session")
def sample_chat_session_fixture(
    session: Session,
    test_tenant: Tenant,
) -> ChatSession:
    """Cria sessão de chat para testes."""
    chat_sess = ChatSession(tenant_id=test_tenant.id)
    session.add(chat_sess)
    session.commit()
    session.refresh(chat_sess)

    # Adicionar algumas mensagens
    msg1 = ChatMessage(
        session_id=chat_sess.id,
        sender="human",
        content="Devo comprar o produto SKU_001?",
        tenant_id=test_tenant.id,
    )
    msg2 = ChatMessage(
        session_id=chat_sess.id,
        sender="agent",
        content="Com base na análise, recomendo aprovar a compra de 100 unidades.",
        tenant_id=test_tenant.id,
    )
    session.add_all([msg1, msg2])
    session.commit()

    return chat_sess


@pytest.fixture(name="sample_agents")
def sample_agents_fixture(
    session: Session,
    test_tenant: Tenant,
) -> list[Agente]:
    """Cria agentes padrão para testes."""
    agents_data = [
        ("Analista de Demanda", "Analisa padrões de demanda e estoque"),
        ("Pesquisador de Mercado", "Pesquisa ofertas e tendências"),
        ("Analista de Logística", "Avalia fornecedores e custos"),
        ("Gerente de Compras", "Consolida análises e decide"),
    ]
    agents = []
    for nome, descricao in agents_data:
        agent = Agente(
            nome=nome,
            descricao=descricao,
            status="active",
            tenant_id=test_tenant.id,
        )
        session.add(agent)
        agents.append(agent)
    session.commit()
    for a in agents:
        session.refresh(a)
    return agents


@pytest.fixture(name="sample_sales_history")
def sample_sales_history_fixture(
    session: Session,
    sample_product: Produto,
    test_tenant: Tenant,
) -> list[VendasHistoricas]:
    """Cria histórico de vendas para testes de ML."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    sales = []
    for i in range(30):
        sale = VendasHistoricas(
            produto_id=sample_product.id,
            data_venda=datetime.now(UTC) - timedelta(days=30 - i),
            quantidade=10 + (i % 5),
            receita=Decimal(str(145.00 + (i % 5) * 14.50)),
            tenant_id=test_tenant.id,
        )
        session.add(sale)
        sales.append(sale)

    session.commit()
    for s in sales:
        session.refresh(s)
    return sales
