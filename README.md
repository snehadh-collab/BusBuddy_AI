# 🚌 BusBuddy AI — Agentic Travel & Smart Coupon Engine

**Submitted by:** Sneha D H 
**Department of Computer Science and Engineering**  
**Vel Tech Multi Tech Dr. Rangarajan Dr. Sakunthala Engineering College**  
**Track:** HCLTech Placement Evaluation — USM + Generative AI  

---

## Overview

**BusBuddy AI** is a dual-layer agentic travel booking and coupon optimization system that goes beyond standard bus booking portals by combining **habit-based personalization**, **deterministic multi-source coupon arbitrage**, **FAISS-backed policy RAG**, **Model Context Protocol (MCP 2.x)** tool exposure, and a **Manifest V3 Chrome Extension** for live `redbus.in` checkout assistance.

---

## Key Features

- **Habit-Driven Bus Recommendations (`busbuddy/recommendations.py`):** Mines historical SQLite bookings to identify preferred routes, bus categories (e.g., AC Sleeper), and departure windows, ranking buses with explainable match scores.
- **Deterministic Coupon Engine & Live Feed Sync (`busbuddy/coupon_engine.py`, `busbuddy/coupon_sync.py`):** Syncs active promotional offers from public aggregators (`redBus Official`, `GrabOn`, `CashKaro`, `CouponDunia`) and strictly validates expiry dates, minimum fare thresholds, user tier eligibility, and max discount caps—eliminating LLM arithmetic hallucinations.
- **Gemini 2.5 Flash Tool-Calling Agent (`busbuddy/agent.py`):** Orchestrates multi-step user requests by invoking verified Python tools (`search_buses`, `recommend_buses`, `find_best_coupon`, `search_travel_faq`) with full execution logs and an offline deterministic fallback.
- **Travel Policy RAG (`busbuddy/rag/retriever.py`):** Embeds cancellation, refund, luggage, and coupon terms using `all-MiniLM-L6-v2` and indexes them in **FAISS** with cosine similarity thresholding.
- **Model Context Protocol Server (`mcp_server/server.py`):** Exposes core travel and coupon tools via the official `mcp` 2.x SDK (`MCPServer`) for external AI clients.
- **Chrome Extension (`app/chrome_extension/`):** Manifest V3 popup overlay for `redbus.in` that ranks eligible offers in real time and auto-fills promo codes at checkout.

---

## Project Structure

```text
BusBuddy_AI/
├── app/
│   ├── main.py                  # Streamlit consumer booking portal & coupon battle UI
│   └── chrome_extension/        # Manifest V3 Chrome Extension for redbus.in
│       ├── manifest.json
│       ├── popup.html
│       └── popup.js
├── busbuddy/
│   ├── config.py                # Environment & path configuration
│   ├── database.py              # SQLite schema & seeded booking/coupon data
│   ├── coupon_engine.py         # Deterministic promo validation & ranking
│   ├── coupon_sync.py           # Multi-source live coupon aggregator & sync
│   ├── recommendations.py       # User habit analysis & bus scoring
│   ├── agent.py                 # Gemini 2.5 Flash tool-calling agent
│   └── rag/
│       └── retriever.py         # FAISS + MiniLM semantic policy retriever
├── data/
│   └── knowledge_base/          # Policy documents for RAG
├── mcp_server/
│   └── server.py                # MCP 2.x tool server
├── tests/                       # Automated pytest suite (13 checks)
└── requirements.txt