from typing import TypedDict, Optional
from langgraph.graph import StateGraph, Node
from app.agents.tools import TOOLS

# Define the state structure for the graph
class PurchaseAnalysisState(TypedDict):
    product_sku: str
    forecast: Optional[dict]
    market_prices: Optional[dict]
    recommendation: Optional[dict]

# Define the first node: Demand Analyst
def demand_analyst_node(state: PurchaseAnalysisState):
    """
    Node to analyze demand and decide if a purchase is necessary.
    """
    product_info = TOOLS["Get Product Info"].run(state["product_sku"])
    product_data = json.loads(product_info)

    if product_data["estoque_atual"] <= product_data["estoque_minimo"]:
        state["forecast"] = TOOLS["Get Forecast"].run(state["product_sku"])
        return "purchase_needed"
    return "no_purchase_needed"

# Define the second node: Market Researcher
def market_researcher_node(state: PurchaseAnalysisState):
    """
    Node to fetch market prices if a purchase is needed.
    """
    market_price = TOOLS["Search Market Price"].run(state["product_sku"])
    state["market_prices"] = json.loads(market_price)
    return "done"

# Instantiate the graph
supply_chain_graph = StateGraph(initial_state=PurchaseAnalysisState)

# Add nodes to the graph
supply_chain_graph.add_node(Node(name="demand_analyst", func=demand_analyst_node))
supply_chain_graph.add_node(Node(name="market_researcher", func=market_researcher_node))

# Define edges between nodes
supply_chain_graph.add_edge("demand_analyst", "market_researcher", condition="purchase_needed")
supply_chain_graph.add_edge("demand_analyst", "END", condition="no_purchase_needed")
supply_chain_graph.add_edge("market_researcher", "END", condition="done")

# Compile the graph
supply_chain_graph.compile()