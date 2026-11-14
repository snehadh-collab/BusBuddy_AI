import re
from typing import Any, Dict, List
from google import genai
from google.genai import types

from busbuddy.config import GEMINI_API_KEY, LLM_AVAILABLE
from busbuddy.recommendations import (
    get_user_profile_and_patterns,
    search_buses,
    recommend_buses,
)
from busbuddy.coupon_engine import get_available_coupons, find_best_coupon
from busbuddy.rag.retriever import query_travel_faq

SYSTEM_INSTRUCTION = """
You are BusBuddy AI, an Agentic AI-powered personalized bus booking and smart savings assistant.
You work alongside bus booking platforms (using simulated sample inventory) to help users save money and book faster.

CRITICAL RULES:
1. NEVER invent bus operators, ticket prices, coupon codes, discount amounts, or travel policies.
2. ALWAYS invoke the provided Python tools to fetch user history, search buses, calculate coupon discounts, or look up travel FAQs.
3. All financial arithmetic and coupon validation are handled by Python tools. Present the exact numbers returned by the tools.
4. Explain WHY you are recommending a bus or coupon (e.g., referencing the user's past AC Sleeper booking habit or comparing competing coupons).
5. Clearly note that fares and schedules are simulated prototype data.
"""


class BusBuddyAgent:
    def __init__(self, user_id: str = "U101"):
        self.user_id = user_id
        self.tool_logs: List[Dict[str, Any]] = []
        self.client = genai.Client(api_key=GEMINI_API_KEY) if LLM_AVAILABLE else None

    def _log_tool(self, tool_name: str, args: Dict[str, Any], output: Any):
        self.tool_logs.append({
            "tool": tool_name,
            "arguments": args,
            "result_preview": str(output)[:350] + ("..." if len(str(output)) > 350 else ""),
        })

    # --- Python Tools Exposed to Gemini ---
    def tool_get_user_profile(self) -> Dict:
        """Retrieve the current user's profile, past booking history, preferred bus type, and average fare."""
        res = get_user_profile_and_patterns(self.user_id)
        # Keep payload concise for LLM context
        summary = {k: v for k, v in res.items() if k != "bookings"}
        summary["recent_bookings_count"] = len(res.get("bookings", []))
        self._log_tool("get_user_profile", {"user_id": self.user_id}, summary)
        return summary

    def tool_search_buses(self, source: str, destination: str, max_budget: float = 0.0, bus_type: str = "ALL") -> List[Dict]:
        """Search simulated bus inventory between source and destination. Pass max_budget=0 for no limit."""
        budget = max_budget if max_budget > 0 else None
        res = search_buses(source=source, destination=destination, max_budget=budget, bus_type=bus_type)
        self._log_tool("search_buses", {"source": source, "destination": destination, "max_budget": budget, "bus_type": bus_type}, res)
        return res

    def tool_recommend_buses(self, source: str = "", destination: str = "", max_budget: float = 0.0) -> Dict:
        """Get personalized bus recommendations ranked by past booking habits, automatically bundled with the best valid coupon."""
        res = recommend_buses(
            user_id=self.user_id,
            source=source or None,
            destination=destination or None,
            max_budget=max_budget if max_budget > 0 else None,
        )
        self._log_tool("recommend_buses", {"source": source, "destination": destination, "max_budget": max_budget}, res)
        return res

    def tool_find_best_coupon(self, base_fare: float, route: str, bus_type: str) -> Dict:
        """Validate all available coupons and compute the highest valid discount and final payable fare."""
        res = find_best_coupon(base_fare=base_fare, route=route, bus_type=bus_type, user_id=self.user_id)
        self._log_tool("find_best_coupon", {"base_fare": base_fare, "route": route, "bus_type": bus_type}, res)
        return res

    def tool_list_all_coupons(self) -> List[Dict]:
        """List all promo coupons in the database along with their eligibility rules."""
        res = get_available_coupons()
        self._log_tool("list_all_coupons", {}, res)
        return res

    def tool_search_travel_faq(self, question: str) -> Dict:
        """Search the RAG travel policy knowledge base for cancellation, refund, luggage, or coupon rules."""
        res = query_travel_faq(question)
        self._log_tool("search_travel_faq", {"question": question}, res)
        return res

    def _local_fallback_response(self, user_message: str) -> str:
        """Deterministic fallback agent when GEMINI_API_KEY is not configured."""
        msg = user_message.lower()

        if any(word in msg for word in ["cancel", "refund", "luggage", "bag", "policy", "boarding", "id"]):
            faq = self.tool_search_travel_faq(user_message)
            if not faq["found"]:
                return faq["answer"]
            snippets = "\n".join(f"- {m['text']} *(Source: {m['source']})*" for m in faq["matches"])
            return f"**[Local Demo Mode – RAG Policy Retrieval]**\n\nHere is what our verified policy documents state:\n{snippets}"

        if "coupon" in msg or "discount" in msg or "save" in msg or "offer" in msg:
            fare_match = re.search(r"(\d{3,4})", msg)
            fare = float(fare_match.group(1)) if fare_match else 1200.0
            route = "Chennai-Bangalore"
            if "coimbatore" in msg:
                route = "Chennai-Coimbatore"
            elif "hyderabad" in msg:
                route = "Chennai-Hyderabad"
            bus_type = "AC Seater" if "seater" in msg else "AC Sleeper"
            res = self.tool_find_best_coupon(base_fare=fare, route=route, bus_type=bus_type)
            return (
                f"**[Local Demo Mode – Deterministic Coupon Agent]**\n\n"
                f"For a **₹{fare:.0f}** `{bus_type}` ticket on **{route}**:\n"
                f"- **Best Valid Coupon:** `{res['best_coupon']}`\n"
                f"- **Discount Applied:** −₹{res['discount_amount']:.0f}\n"
                f"- **Final Payable Fare:** **₹{res['final_fare']:.0f}**\n"
                f"- **Why:** {res['selection_reason']}"
            )

        # Default: personalized bus recommendation
        recs = self.tool_recommend_buses()
        patterns = recs["user_patterns"]
        top = recs["recommendations"][0]
        return (
            f"**[Local Demo Mode – Personalized Travel Agent]**\n\n"
            f"Based on your booking history, you frequently travel **{patterns['top_route']}** "
            f"and prefer **{patterns['preferred_bus_type']}** ({patterns['bus_type_frequency']}).\n\n"
            f"**Top Recommended Option (Simulated Data):**\n"
            f"- **Operator:** {top['operator']} ({top['bus_type']} • {top['departure_time']})\n"
            f"- **Base Fare:** ₹{top['base_fare']:.0f}\n"
            f"- **Best Coupon Applied:** `{top['best_coupon']}` (−₹{top['discount_amount']:.0f})\n"
            f"- **Final Estimated Fare:** **₹{top['final_fare']:.0f}**\n"
            f"- **Why:** {'; '.join(top['why_recommended'])}"
        )

    def run(self, user_message: str) -> Dict[str, Any]:
        """Execute an agent turn with automatic tool calling and return response + tool execution log."""
        self.tool_logs = []

        if not self.client:
            reply = self._local_fallback_response(user_message)
            return {"response": reply, "tool_logs": self.tool_logs, "mode": "Local Fallback Mode"}

        tools = [
            self.tool_get_user_profile,
            self.tool_search_buses,
            self.tool_recommend_buses,
            self.tool_find_best_coupon,
            self.tool_list_all_coupons,
            self.tool_search_travel_faq,
        ]

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools,
                    temperature=0.2,
                ),
            )
            return {
                "response": response.text or "No response generated.",
                "tool_logs": self.tool_logs,
                "mode": "Gemini 2.5 Flash Agentic Tool Calling",
            }
        except Exception as exc:
            # Graceful fallback if quota/network issue occurs during live demo
            fallback_reply = self._local_fallback_response(user_message)
            return {
                "response": f"{fallback_reply}\n\n*(Note: Fell back to local mode due to API error: {exc})*",
                "tool_logs": self.tool_logs,
                "mode": "Fallback (API Error Handled)",
            }