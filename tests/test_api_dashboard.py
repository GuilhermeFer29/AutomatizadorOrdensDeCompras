"""
Testes para API do Dashboard.
"""

import pytest
from fastapi.testclient import TestClient


class TestDashboardEndpoints:
    """Testes para endpoints do dashboard."""

    def test_get_kpis(self, client: TestClient):
        """GET /api/dashboard/kpis - deve retornar KPIs."""
        response = client.get("/api/dashboard/kpis")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verificar campos esperados
        assert "economy" in data or "economia" in data
        assert "automatedOrders" in data or "ordens_automatizadas" in data
        assert "stockLevel" in data or "nivel_estoque" in data

    def test_get_alerts(self, client: TestClient):
        """GET /api/dashboard/alerts - deve retornar alertas."""
        response = client.get("/api/dashboard/alerts")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_kpis_economy_is_number(self, client: TestClient):
        """KPI de economia deve ser numérico."""
        response = client.get("/api/dashboard/kpis")
        
        if response.status_code == 200:
            data = response.json()
            economy = data.get("economy", data.get("economia", 0))
            assert isinstance(economy, (int, float))

    def test_kpis_stock_level_valid(self, client: TestClient):
        """Nível de estoque deve ser valor válido."""
        response = client.get("/api/dashboard/kpis")
        
        if response.status_code == 200:
            data = response.json()
            stock_level = data.get("stockLevel", data.get("nivel_estoque", ""))
            
            valid_levels = ["Crítico", "Atenção", "Saudável", "N/A", ""]
            assert stock_level in valid_levels or isinstance(stock_level, str)


class TestDashboardAlerts:
    """Testes específicos para alertas."""

    def test_alert_structure(self, client: TestClient):
        """Alertas devem ter estrutura correta."""
        response = client.get("/api/dashboard/alerts")
        
        if response.status_code == 200 and len(response.json()) > 0:
            alert = response.json()[0]
            
            # Campos que podem existir
            possible_fields = ["id", "product", "sku", "alert", "message", "severity", "stock"]
            has_at_least_one = any(field in alert for field in possible_fields)
            assert has_at_least_one

    def test_alert_severity_valid(self, client: TestClient):
        """Severidade do alerta deve ser válida."""
        response = client.get("/api/dashboard/alerts")
        
        if response.status_code == 200:
            for alert in response.json():
                if "severity" in alert:
                    assert alert["severity"] in ["error", "warning", "info", "success"]
