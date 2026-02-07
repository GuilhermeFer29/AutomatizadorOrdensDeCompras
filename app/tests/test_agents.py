"""Tests for agents initialization."""

import os
from unittest.mock import patch

from agno.team import Team

from app.agents.supply_chain_team import create_supply_chain_team


@patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"})
def test_create_supply_chain_team_structure():
    """Test if supply chain team creates correct agents."""

    # We mock the Gemini LLM creation to avoid real API calls during init
    with patch("app.agents.supply_chain_team.get_gemini_for_fast_agents"), \
         patch("app.agents.supply_chain_team.get_gemini_for_reasoning_agents"):

        team = create_supply_chain_team()

        assert isinstance(team, Team)
        # Check if we have the expected agents
        assert len(team.agents) == 4

        agent_names = [agent.name for agent in team.agents]
        assert "Analista de Demanda" in agent_names
        assert "Pesquisador de Mercado" in agent_names
        assert "Analista de Logística" in agent_names
        assert "Gerente de Compras" in agent_names
