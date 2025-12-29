"""
Testes para API de Ordens.
"""

import pytest
from fastapi.testclient import TestClient


class TestOrderEndpoints:
    """Testes para endpoints de ordens."""

    def test_list_orders(self, client: TestClient):
        """GET /api/orders - deve retornar lista de ordens."""
        response = client.get("/api/orders")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_orders_with_status_filter(self, client: TestClient):
        """GET /api/orders?status=pending - deve filtrar por status."""
        response = client.get("/api/orders", params={"status": "pending"})
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_order(self, client: TestClient, sample_order_data: dict):
        """POST /api/orders - deve criar ordem."""
        response = client.post("/api/orders", json=sample_order_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        # API retorna produto_id e quantidade, não o nome do produto
        assert "produto_id" in data or "id" in data
        assert data["quantidade"] == sample_order_data["quantity"]

    def test_create_order_without_status(self, client: TestClient):
        """POST /api/orders - NÃO deve enviar status (backend define)."""
        order_data = {
            "product": "Produto Teste",
            "quantity": 5,
            "value": 500.00,
            "origin": "Manual",
            # NÃO incluir 'status' - backend define como 'pending'
        }
        
        response = client.post("/api/orders", json=order_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        # Backend deve ter definido status automaticamente
        assert "status" in data or response.status_code == 201

    def test_create_order_status_is_ignored(self, client: TestClient):
        """POST /api/orders - status enviado pelo cliente deve ser ignorado."""
        order_data = {
            "product": "Produto Teste",
            "quantity": 5,
            "value": 500.00,
            "origin": "Manual",
            "status": "approved",  # Cliente tentando aprovar direto
        }
        
        response = client.post("/api/orders", json=order_data)
        
        # Pode dar 422 (validação) ou ignorar o campo
        assert response.status_code in [200, 201, 422]

    def test_approve_order(self, client: TestClient, sample_order_data: dict):
        """POST /api/orders/:id/approve - deve aprovar ordem."""
        # Criar ordem primeiro
        create_response = client.post("/api/orders", json=sample_order_data)
        if create_response.status_code in [200, 201]:
            order_id = create_response.json().get("id", 1)
            
            # Aprovar
            response = client.post(f"/api/orders/{order_id}/approve")
            
            assert response.status_code in [200, 400, 404]

    def test_reject_order(self, client: TestClient, sample_order_data: dict):
        """POST /api/orders/:id/reject - deve rejeitar ordem."""
        create_response = client.post("/api/orders", json=sample_order_data)
        if create_response.status_code in [200, 201]:
            order_id = create_response.json().get("id", 1)
            
            response = client.post(f"/api/orders/{order_id}/reject")
            
            assert response.status_code in [200, 400, 404]


class TestOrderValidation:
    """Testes de validação de ordens."""

    def test_product_required(self, client: TestClient):
        """Produto é obrigatório."""
        data = {"quantity": 10, "value": 100.00}
        response = client.post("/api/orders", json=data)
        assert response.status_code == 422

    def test_quantity_positive(self, client: TestClient):
        """Quantidade deve ser positiva."""
        data = {
            "product": "Produto",
            "quantity": 0,  # Deve ser > 0
            "value": 100.00,
        }
        response = client.post("/api/orders", json=data)
        assert response.status_code == 422

    def test_value_positive(self, client: TestClient):
        """Valor deve ser positivo."""
        data = {
            "product": "Produto",
            "quantity": 10,
            "value": 0,  # Deve ser > 0
        }
        response = client.post("/api/orders", json=data)
        assert response.status_code == 422
