"""Tests for agent tools."""

from decimal import Decimal

# Mocking get_session to return our test session
from unittest.mock import patch

from sqlmodel import Session

from app.agents.tools_secure import get_product_info
from app.models.models import Produto


def test_get_product_info(session: Session):
    """Test get_product_info tool."""
    # Seed data
    product = Produto(
        sku="TEST-SKU-001",
        nome="Test Product",
        categoria="Test Category",
        estoque_atual=100,
        estoque_minimo=20,
        custo_unitario=Decimal("10.50")
    )
    session.add(product)
    session.commit()

    # We need to patch the session used inside the tool
    # Since get_product_info likely creates its own session or uses a dependency,
    # we might need to adjust the tool code or patch where it gets the session.
    # Assuming tools_secure.py uses a direct session creation or we can patch it

    with patch("app.agents.tools_secure.get_sync_engine") as mock_engine:
        # Mocking the session context manager used in tools_secure.py
        mock_engine.return_value = session.get_bind()

        # Actually, tools_secure.py uses `with Session(engine) as session:`
        # We need to patch Session in tools_secure.py to return our test session
        with patch("app.agents.tools_secure.Session", return_value=session):
            result = get_product_info("TEST-SKU-001")

            assert "Test Product" in result
            assert "100" in result  # Stock
            assert "TEST-SKU-001" in result
