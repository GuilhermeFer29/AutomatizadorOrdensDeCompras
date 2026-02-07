"""Tests for API endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.models import ChatMessage, ChatSession, PrecosHistoricos, Produto


def test_read_products_empty(client: TestClient):
    """Test reading products when db is empty."""
    response = client.get("/api/products/")
    assert response.status_code == 200
    assert response.json() == []

def test_create_product(client: TestClient):
    """Test creating a new product."""
    response = client.post(
        "/api/products/",
        json={
            "sku": "NEW-SKU-001",
            "name": "New Product",
            "price": 50.0,
            "stock": 100
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "NEW-SKU-001"
    assert data["nome"] == "New Product"

def test_read_products_with_data(client: TestClient, session: Session):
    """Test reading products with seeded data."""
    # Seed data
    product = Produto(sku="EXISTING-SKU", nome="Existing Product", estoque_atual=10, estoque_minimo=5, categoria="Test")
    session.add(product)
    session.commit()

    response = client.get("/api/products/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["sku"] == "EXISTING-SKU"

def test_get_product_price_history(client: TestClient, session: Session):
    """Test getting price history."""
    product = Produto(sku="HistSKU", nome="Hist Product", estoque_atual=10, categoria="Test")
    session.add(product)
    session.commit()

    # Add history
    price = PrecosHistoricos(produto_id=product.id, preco=100.0)
    session.add(price)
    session.commit()

    response = client.get("/api/products/HistSKU/price-history")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["price"] == 100.0

def test_create_chat_session(client: TestClient):
    """Test creating a chat session."""
    response = client.post("/api/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "criado_em" in data

@patch("app.routers.api_chat_router.process_user_message")
def test_post_chat_message(mock_process, client: TestClient, session: Session):
    """Test posting a chat message."""
    # Create session first
    chat_session = ChatSession()
    session.add(chat_session)
    session.commit()

    # Mock return of process_user_message
    mock_response = ChatMessage(
        session_id=chat_session.id,
        sender="assistant",
        content="Hello, I am a mock agent.",
        metadata_json='{"type": "text"}'
    )
    mock_process.return_value = mock_response

    response = client.post(
        f"/api/chat/sessions/{chat_session.id}/messages",
        json={"content": "Hello agent"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello, I am a mock agent."
    assert data["sender"] == "assistant"
