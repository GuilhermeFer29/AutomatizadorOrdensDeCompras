"""
Supply Chain Graph - LangGraph implementation conforme documentação oficial.

Referência: https://docs.langchain.com/oss/python/langgraph/graph-api
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph


# Define the state structure for the graph
class PurchaseAnalysisState(TypedDict):
    product_sku: str
    forecast: dict | None
    market_prices: dict | None
    recommendation: dict | None

# Define nodes
def demand_analyst_node(state: PurchaseAnalysisState) -> PurchaseAnalysisState:
    """Analyze demand and decide if a purchase is necessary."""
    # Placeholder implementation
    return {
        "product_sku": state["product_sku"],
        "forecast": None,
        "market_prices": None,
        "recommendation": None
    }

def market_researcher_node(state: PurchaseAnalysisState) -> PurchaseAnalysisState:
    """Fetch market prices if a purchase is needed."""
    return state

# Instantiate the graph conforme documentação oficial
supply_chain_graph = StateGraph(PurchaseAnalysisState)

# Add nodes to the graph (sintaxe correta do LangGraph)
supply_chain_graph.add_node("demand_analyst", demand_analyst_node)
supply_chain_graph.add_node("market_researcher", market_researcher_node)

# Set entry point
supply_chain_graph.set_entry_point("demand_analyst")

# Define edges between nodes (sintaxe correta)
supply_chain_graph.add_edge("demand_analyst", "market_researcher")
supply_chain_graph.add_edge("market_researcher", END)

# Compile the graph
supply_chain_graph = supply_chain_graph.compile()
