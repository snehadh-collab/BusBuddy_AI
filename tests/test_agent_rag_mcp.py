import asyncio
from busbuddy.database import init_db
from busbuddy.rag.retriever import query_travel_faq
from busbuddy.agent import BusBuddyAgent
from mcp_server.server import mcp


def setup_module():
    init_db(force_reseed=True)


def test_rag_relevant_and_irrelevant_queries():
    relevant = query_travel_faq("Can I cancel my ticket 2 hours before departure?")
    assert relevant["found"] is True
    assert any("cancellation" in s for s in relevant["sources"])

    irrelevant = query_travel_faq("What is the recipe for chicken biryani?")
    assert irrelevant["found"] is False


def test_agent_tool_execution_and_fallback():
    agent = BusBuddyAgent(user_id="U101")
    result = agent.run("Find me a coupon for my 1200 ticket on Chennai-Bangalore AC Sleeper")
    assert "BLR200" in result["response"]
    assert len(result["tool_logs"]) >= 1


def test_mcp_server_tools_registered():
    tools = asyncio.run(mcp.list_tools())
    tool_names = [t.name for t in tools]
    assert "mcp_find_best_coupon" in tool_names
    assert "mcp_recommend_buses" in tool_names
    assert "mcp_get_travel_faq" in tool_names