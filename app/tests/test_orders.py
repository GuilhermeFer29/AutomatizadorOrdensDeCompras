"""Tests for order endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_create_order_valid(client: TestClient):
    """Test creating a valid order."""
    response = client.post(
        "/api/orders/",
        json={
            "product": "Produto Teste",
            "quantity": 10,
            "value": 100.50,
            "origin": "Manual"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["quantidade"] == 10
    assert data["status"] == "pending"


def test_create_order_invalid_quantity(client: TestClient):
    """Test creating order with invalid quantity (zero or negative)."""
    response = client.post(
        "/api/orders/",
        json={
            "product": "Produto Teste",
            "quantity": 0,
            "value": 100.50,
            "origin": "Manual"
        }
    )
    assert response.status_code == 422  # Validation error


def test_create_order_invalid_value(client: TestClient):
    """Test creating order with invalid value (zero or negative)."""
    response = client.post(
        "/api/orders/",
        json={
            "product": "Produto Teste",
            "quantity": 10,
            "value": -50.0,
            "origin": "Manual"
        }
    )
    assert response.status_code == 422  # Validation error


def test_create_order_empty_product(client: TestClient):
    """Test creating order with empty product name."""
    response = client.post(
        "/api/orders/",
        json={
            "product": "",
            "quantity": 10,
            "value": 100.50,
            "origin": "Manual"
        }
    )
    assert response.status_code == 422  # Validation error


def test_approve_order(client: TestClient):
    """Test approving a pending order."""
    # Create order
    create_response = client.post(
        "/api/orders/",
        json={
            "product": "Produto para Aprovar",
            "quantity": 5,
            "value": 250.00,
            "origin": "Manual"
        }
    )
    order_id = create_response.json()["id"]
    
    # Approve order
    response = client.post(f"/api/orders/{order_id}/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"


def test_approve_nonexistent_order(client: TestClient):
    """Test approving a nonexistent order."""
    response = client.post("/api/orders/99999/approve")
    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"]


def test_reject_order(client: TestClient):
    """Test rejecting a pending order."""
    # Create order
    create_response = client.post(
        "/api/orders/",
        json={
            "product": "Produto para Rejeitar",
            "quantity": 3,
            "value": 150.00,
            "origin": "Manual"
        }
    )
    order_id = create_response.json()["id"]
    
    # Reject order
    response = client.post(f"/api/orders/{order_id}/reject")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_reject_nonexistent_order(client: TestClient):
    """Test rejecting a nonexistent order."""
    response = client.post("/api/orders/99999/reject")
    assert response.status_code == 404
    assert "não encontrada" in response.json()["detail"]


def test_approve_already_approved_order(client: TestClient):
    """Test approving an already approved order."""
    # Create and approve order
    create_response = client.post(
        "/api/orders/",
        json={
            "product": "Produto Duplo Aprovado",
            "quantity": 2,
            "value": 100.00,
            "origin": "Manual"
        }
    )
    order_id = create_response.json()["id"]
    client.post(f"/api/orders/{order_id}/approve")
    
    # Try to approve again
    response = client.post(f"/api/orders/{order_id}/approve")
    assert response.status_code == 400
    assert "pendentes" in response.json()["detail"]


def test_get_orders(client: TestClient):
    """Test retrieving orders."""
    # Create some orders
    client.post(
        "/api/orders/",
        json={
            "product": "Produto 1",
            "quantity": 5,
            "value": 100.00,
            "origin": "Manual"
        }
    )
    
    # Get orders
    response = client.get("/api/orders/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_orders_by_status(client: TestClient):
    """Test filtering orders by status."""
    # Create and approve an order
    create_response = client.post(
        "/api/orders/",
        json={
            "product": "Produto Aprovado",
            "quantity": 10,
            "value": 500.00,
            "origin": "Manual"
        }
    )
    order_id = create_response.json()["id"]
    client.post(f"/api/orders/{order_id}/approve")
    
    # Get approved orders
    response = client.get("/api/orders/?status=approved")
    assert response.status_code == 200
    data = response.json()
    assert all(order["status"] == "approved" for order in data)
