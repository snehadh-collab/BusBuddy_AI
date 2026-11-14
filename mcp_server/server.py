from mcp.server.mcpserver import MCPServer
from busbuddy.database import init_db
from busbuddy.recommendations import (
    get_user_profile_and_patterns,
    search_buses,
    recommend_buses,
)
from busbuddy.coupon_engine import find_best_coupon
from busbuddy.rag.retriever import query_travel_faq

# Initialize database on server startup
init_db()

# Create official MCP 2.x Server instance
mcp = MCPServer("BusBuddy-AI-MCP-Server")


@mcp.tool()
def mcp_get_user_profile(user_id: str = "U101") -> dict:
    """Retrieve a user's travel profile, frequent routes, preferred bus type, and average ticket spend."""
    return get_user_profile_and_patterns(user_id)


@mcp.tool()
def mcp_search_buses(source: str, destination: str, max_budget: float = 0.0, bus_type: str = "ALL") -> list:
    """Search simulated bus schedules and fares between two cities."""
    budget = max_budget if max_budget > 0 else None
    return search_buses(source=source, destination=destination, max_budget=budget, bus_type=bus_type)


@mcp.tool()
def mcp_recommend_buses(user_id: str = "U101", source: str = "", destination: str = "") -> dict:
    """Recommend personalized buses based on booking history and apply the highest valid discount coupon."""
    return recommend_buses(user_id=user_id, source=source or None, destination=destination or None)


@mcp.tool()
def mcp_find_best_coupon(base_fare: float, route: str, bus_type: str, user_id: str = "U101") -> dict:
    """Validate available promo codes against route, bus type, expiry, and minimum spend to find maximum savings."""
    return find_best_coupon(base_fare=base_fare, route=route, bus_type=bus_type, user_id=user_id)


@mcp.tool()
def mcp_get_travel_faq(question: str) -> dict:
    """Query the RAG policy knowledge base for cancellation, refund, luggage, or coupon terms."""
    return query_travel_faq(question)


if __name__ == "__main__":
    mcp.run()