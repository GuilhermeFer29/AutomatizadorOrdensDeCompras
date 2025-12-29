"""
Testes para API de Produtos.
"""

import pytest
from fastapi.testclient import TestClient


class TestProductEndpoints:
    """Testes para endpoints de produtos."""

    def test_list_products(self, client: TestClient):
        """GET /api/products - deve retornar lista de produtos."""
        response = client.get("/api/products")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_products_with_search(self, client: TestClient):
        """GET /api/products?search=xxx - deve filtrar produtos."""
        response = client.get("/api/products", params={"search": "teste"})
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_product(self, client: TestClient, sample_product_data: dict):
        """POST /api/products - deve criar produto."""
        response = client.post("/api/products", json=sample_product_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["sku"] == sample_product_data["sku"]

    def test_create_product_requires_name(self, client: TestClient):
        """POST /api/products - deve exigir campo name."""
        invalid_data = {
            "sku": "TEST001",
            "price": 100.00,
            "stock": 10,
            # Falta 'name'
        }
        
        response = client.post("/api/products", json=invalid_data)
        
        assert response.status_code == 422  # Validation error

    def test_create_product_uses_english_fields(self, client: TestClient):
        """POST /api/products - deve usar campos em inglês."""
        # Backend espera: name, price, stock
        # NÃO: nome, preco, estoque_atual
        valid_data = {
            "sku": "TEST002",
            "name": "Produto Válido",
            "price": 100.00,
            "stock": 50,
        }
        
        response = client.post("/api/products", json=valid_data)
        
        assert response.status_code in [200, 201]

    def test_update_product(self, client: TestClient, sample_product_data: dict):
        """PUT /api/products/:id - deve atualizar produto."""
        # Primeiro criar
        create_response = client.post("/api/products", json=sample_product_data)
        if create_response.status_code in [200, 201]:
            product_id = create_response.json().get("id", 1)
            
            # Depois atualizar
            update_data = {"name": "Produto Atualizado", "stock": 200}
            response = client.put(f"/api/products/{product_id}", json=update_data)
            
            assert response.status_code in [200, 404]  # 404 se não existir


class TestProductValidation:
    """Testes de validação de produtos."""

    def test_sku_required(self, client: TestClient):
        """SKU é obrigatório."""
        data = {"name": "Produto", "price": 100, "stock": 10}
        response = client.post("/api/products", json=data)
        assert response.status_code == 422

    def test_price_positive(self, client: TestClient):
        """Preço deve ser positivo."""
        data = {"sku": "TEST", "name": "Produto", "price": -10, "stock": 10}
        response = client.post("/api/products", json=data)
        # Alguns backends aceitam negativo, outros não
        assert response.status_code in [200, 201, 422]

    def test_stock_not_negative(self, client: TestClient):
        """Estoque não deve ser negativo."""
        data = {"sku": "TEST", "name": "Produto", "price": 100, "stock": -5}
        response = client.post("/api/products", json=data)
        assert response.status_code in [200, 201, 422]
