"""Tests for agent tools."""

import pytest
from decimal import Decimal
from sqlmodel import Session

from app.models.models import Produto, PrecosHistoricos, Fornecedor
from app.agents.tools import get_product_info, SupplyChainToolkit
from app.core.database import get_session

# Mocking get_session to return our test session
from unittest.mock import patch, MagicMock

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
    # Assuming tools.py uses a direct session creation or we can patch 'app.agents.tools.Session'
    
    with patch("app.agents.tools.engine") as mock_engine:
        # Mocking the session context manager used in tools.py
        mock_engine.connect.return_value.__enter__.return_value = session
        
        # Actually, tools.py usually uses `with Session(engine) as session:`
        # We need to patch Session in tools.py to return our test session
        with patch("app.agents.tools.Session", return_value=session):
            result = get_product_info("TEST-SKU-001")
            
            assert "Test Product" in result
            assert "100" in result  # Stock
            assert "TEST-SKU-001" in result

def test_supply_chain_toolkit_lookup(session: Session):
    """Test SupplyChainToolkit lookup_product."""
    # Seed data
    product = Produto(
        sku="TOOL-SKU-001",
        nome="Toolkit Product",
        estoque_atual=50,
        categoria="Tools"
    )
    session.add(product)
    session.commit()
    
    toolkit = SupplyChainToolkit()
    # Mocking session inside the method if it opens one, or if it uses engine
    with patch("app.agents.tools.Session", return_value=session):
        result = toolkit.lookup_product("TOOL-SKU-001")
        
        # Result should be a JSON string or dict
        assert "Toolkit Product" in result
        assert "50" in result
