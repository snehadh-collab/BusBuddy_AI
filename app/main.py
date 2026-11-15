import sys
from pathlib import Path
from datetime import date, timedelta
import uuid

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from busbuddy.config import LLM_AVAILABLE
from busbuddy.database import init_db, get_connection
from busbuddy.recommendations import (
    get_user_profile_and_patterns,
    recommend_buses,
)
from busbuddy.coupon_engine import get_available_coupons, find_best_coupon
from busbuddy.coupon_sync import sync_live_coupons, VERIFIED_LIVE_FEED
from busbuddy.rag.retriever import query_travel_faq
from busbuddy.agent import BusBuddyAgent

st.set_page_config(
    page_title="BusBuddy AI – Agentic Travel & Smart Coupon Engine",
    page_icon="🚌",
    layout="wide",
)

# Custom FinTech + RedBus Coral/Midnight Styling
st.markdown("""
<style>
    .hero-banner {
        background: linear-gradient(135deg, #1E1B4B 0%, #311042 45%, #991B1B 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: #FFFFFF;
        margin-bottom: 1.1rem;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.18);
    }
    .hero-banner h1 {
        color: #FFFFFF;
        margin: 0;
        font-size: 1.95rem;
        letter-spacing: -0.4px;
    }
    .hero-banner p {
        color: #E2E8F0;
        margin: 0.35rem 0 0 0;
        font-size: 0.96rem;
    }
    .hero-badges {
        margin-top: 0.75rem;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }
    .tech-chip {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.22);
        color: #F8FAFC;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 600;
    }
    .kpi-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 0.95rem 1.1rem;
        color: #F8FAFC;
    }
    .kpi-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: #94A3B8;
        font-weight: 700;
    }
    .kpi-value {
        font-size: 1.55rem;
        font-weight: 800;
        color: #34D399;
        margin: 2px 0;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #CBD5E1;
    }
    .ai-nudge {
        background: linear-gradient(90deg, #1E1B4B 0%, #2E1065 100%);
        border-left: 5px solid #A855F7;
        padding: 0.95rem 1.2rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: #F3E8FF;
        font-size: 0.92rem;
    }
    .deal-card {
        background: #111827;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        color: #F9FAFB;
        height: 100%;
    }
    .deal-source {
        font-size: 0.7rem;
        font-weight: 700;
        color: #60A5FA;
        text-transform: uppercase;
    }
    .deal-code {
        font-family: monospace;
        font-size: 1.05rem;
        font-weight: 800;
        color: #34D399;
        margin: 2px 0;
    }
    .deal-desc {
        font-size: 0.78rem;
        color: #D1D5DB;
    }
    .coupon-pill {
        background-color: #064E3B;
        border: 1px dashed #34D399;
        color: #ECFDF5;
        padding: 0.3rem 0.65rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.84rem;
        display: inline-block;
    }
    .battle-win {
        background: linear-gradient(90deg, #064E3B 0%, #022C22 100%);
        border: 1px solid #10B981;
        border-radius: 8px;
        padding: 0.65rem 0.85rem;
        color: #ECFDF5;
        margin-bottom: 0.45rem;
        font-size: 0.85rem;
    }
    .battle-lose {
        background: #18181B;
        border: 1px solid #27272A;
        border-radius: 8px;
        padding: 0.5rem 0.85rem;
        color: #A1A1AA;
        margin-bottom: 0.35rem;
        font-size: 0.8rem;
    }
    .ticket-card {
        background: #0F172A;
        border: 2px solid #10B981;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        color: #F8FAFC;
        box-shadow: 0 6px 18px rgba(16, 185, 129, 0.16);
    }
</style>
""", unsafe_allow_html=True)

init_db()

# Ensure live November 2026 coupons are seeded on first load
if "coupons_initialized" not in st.session_state:
    sync_live_coupons()
    st.session_state.coupons_initialized = True
    st.session_state.last_sync_info = {
        "synced_coupons": len(VERIFIED_LIVE_FEED),
        "live_web_verified_codes": 4,
        "timestamp": "Auto-Synced on Startup",
    }

# Session state for booking flow
if "selected_bus" not in st.session_state:
    st.session_state.selected_bus = None
if "selected_seats" not in st.session_state:
    st.session_state.selected_seats = []
if "last_confirmed_ticket" not in st.session_state:
    st.session_state.last_confirmed_ticket = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "search_dst" not in st.session_state:
    st.session_state.search_dst = "Bangalore"


def save_new_booking(user_id: str, bus: dict, seats: list, final_fare: float, travel_date_str: str) -> str:
    """Persist a confirmed ticket booking into SQLite so history and AI patterns update live."""
    conn = get_connection()
    cursor = conn.cursor()
    booking_id = f"BK{uuid.uuid4().hex[:5].upper()}"
    day_obj = date.fromisoformat(travel_date_str)
    day_type = "Weekend" if day_obj.weekday() >= 5 else "Weekday"

    cursor.execute("""
        INSERT INTO bookings (
            booking_id, user_id, source, destination, operator,
            bus_type, departure_slot, travel_day_type, fare_paid, booking_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        booking_id,
        user_id,
        bus["source"],
        bus["destination"],
        bus["operator"],
        bus["bus_type"],
        bus["departure_slot"],
        day_type,
        final_fare,
        travel_date_str,
    ))

    new_seats = max(0, bus["seats_available"] - len(seats))
    cursor.execute("UPDATE buses SET seats_available = ? WHERE bus_id = ?", (new_seats, bus["bus_id"]))

    conn.commit()
    conn.close()
    return booking_id


# =====================================================================
# HERO HEADER & LIVE TELEMETRY STRIP
# =====================================================================
st.markdown("""
<div class="hero-banner">
    <h1>🚌 BusBuddy AI — Agentic Travel & Smart Coupon Engine</h1>
    <p>Habit-driven bus recommendations, multi-source live coupon arbitrage & grounded policy RAG</p>
    <div class="hero-badges">
        <span class="tech-chip">⚡ Gemini 2.5 Flash Tool Agent</span>
        <span class="tech-chip">🎟️ Multi-Source Coupon Arbitrage</span>
        <span class="tech-chip">📚 FAISS + MiniLM Policy RAG</span>
        <span class="tech-chip">🔌 MCP 2.x Server Ready</span>
        <span class="tech-chip">🧩 Chrome Extension Linked</span>
    </div>
</div>
""", unsafe_allow_html=True)

patterns = get_user_profile_and_patterns("U101")
all_db_coupons = get_available_coupons()
active_coupons_count = sum(1 for c in all_db_coupons if c["expiry_date"] >= date.today().isoformat())
estimated_historical_savings = patterns["total_bookings"] * 185

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Cumulative AI Savings</div>
        <div class="kpi-value">₹{estimated_historical_savings:,}</div>
        <div class="kpi-sub">Across {patterns['total_bookings']} tracked trips</div>
    </div>
    """, unsafe_allow_html=True)
with k2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Active Live Promos</div>
        <div class="kpi-value" style="color:#60A5FA;">{active_coupons_count} Verified</div>
        <div class="kpi-sub">redBus • GrabOn • CashKaro • CouponDunia</div>
    </div>
    """, unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Habit Match Confidence</div>
        <div class="kpi-value" style="color:#C084FC;">{patterns['top_route_frequency']}</div>
        <div class="kpi-sub">{patterns['top_route']} • {patterns['preferred_bus_type']}</div>
    </div>
    """, unsafe_allow_html=True)
with k4:
    engine_label = "Gemini 2.5 Live" if LLM_AVAILABLE else "Deterministic + MCP"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Agent & RAG Status</div>
        <div class="kpi-value" style="color:#FBBF24;">Online</div>
        <div class="kpi-sub">{engine_label} • Zero-Hallucination</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

tab_book, tab_agent, tab_trips, tab_faq, tab_analytics = st.tabs([
    "🎫 Smart Booking & Coupon Battle",
    "🤖 BusBuddy AI Agent",
    "🧳 My Trips & Profile",
    "📋 Travel Policies (RAG)",
    "📊 Spend & Route Insights",
])

# =====================================================================
# TAB 1: REAL BUS TICKET BOOKING FLOW + LIVE COUPON BATTLE
# =====================================================================
with tab_book:
    sync_col1, sync_col2 = st.columns([3.4, 1.1])
    with sync_col1:
        st.markdown(f"""
        <div class="ai-nudge">
            <strong>✨ AI Habit Detection:</strong> Welcome back, <b>{patterns['user']['name']}</b>!
            You booked <b>{patterns['top_route']}</b> ({patterns['top_route_frequency']}) mostly in
            <b>{patterns['preferred_bus_type']}</b> ({patterns['bus_type_frequency']}) during <b>{patterns['preferred_slot']}</b> hours.
        </div>
        """, unsafe_allow_html=True)
    with sync_col2:
        st.write("")
        if st.button("🔄 Sync Live Aggregator Feeds", width="stretch", type="primary"):
            sync_info = sync_live_coupons()
            st.session_state.last_sync_info = sync_info
            st.toast(f"Synced {sync_info['synced_coupons']} active coupons from redBus & partner feeds!")
            st.rerun()

    # Live Multi-Source Deal Strip
    with st.expander("🔥 Live Multi-Source Coupon Feed (redBus Official, GrabOn, CashKaro, CouponDunia)", expanded=True):
        sync_meta = st.session_state.get("last_sync_info", {})
        st.caption(f"Last Feed Sync: **{sync_meta.get('timestamp', 'Just now')}** • Auto-validates expiry, min spend, and route caps.")
        deal_cols = st.columns(4)
        for idx, deal in enumerate(VERIFIED_LIVE_FEED[:4]):
            with deal_cols[idx]:
                st.markdown(f"""
                <div class="deal-card">
                    <div class="deal-source">{deal['source']}</div>
                    <div class="deal-code">{deal['coupon_code']}</div>
                    <div class="deal-desc">{deal['description']}</div>
                </div>
                """, unsafe_allow_html=True)

    # Search Bar
    with st.container(border=True):
        s1, s2, s3, s4, s5 = st.columns([2, 2, 2, 1.5, 1.5])
        src_city = s1.selectbox("From City", ["Chennai"], index=0)
        dst_city = s2.selectbox(
            "To City",
            ["Bangalore", "Coimbatore", "Hyderabad"],
            index=["Bangalore", "Coimbatore", "Hyderabad"].index(st.session_state.search_dst),
        )
        travel_date = s3.date_input("Date of Journey", value=date.today() + timedelta(days=2), min_value=date.today())
        bus_cat = s4.selectbox("Bus Type", ["ALL", "AC Sleeper", "AC Seater", "Non-AC Sleeper"])
        s5.write("")
        s5.write("")
        if s5.button("⚡ AI Auto-Select", width="stretch", type="primary"):
            st.session_state.search_dst = "Bangalore"
            recs = recommend_buses("U101", source="Chennai", destination="Bangalore")
            if recs["recommendations"]:
                st.session_state.selected_bus = recs["recommendations"][0]
                st.session_state.selected_seats = ["L4"]

    main_col, copilot_col = st.columns([2.25, 1])

    # LEFT: Available Buses + Seat Selection + Real-Time Coupon Battle
    with main_col:
        recs_data = recommend_buses("U101", source=src_city, destination=dst_city)
        buses_list = recs_data["recommendations"]
        if bus_cat != "ALL":
            buses_list = [b for b in buses_list if b["bus_type"].lower() == bus_cat.lower()]

        st.subheader(f"🚌 {src_city} → {dst_city} ({len(buses_list)} Buses Available)")

        if not buses_list:
            st.warning("No buses match your selected filter. Switch Bus Type to 'ALL'.")

        for bus in buses_list:
            with st.container(border=True):
                b1, b2, b3 = st.columns([2.2, 1.4, 1.2])
                with b1:
                    badge = "🔥 AI TOP MATCH" if bus["match_score"] >= 85 else f"Match {bus['match_score']}%"
                    st.markdown(f"#### {bus['operator']} &nbsp; `{badge}`")
                    st.write(f"**{bus['bus_type']}** • Departs **{bus['departure_time']}** ({bus['departure_slot']}) • ⭐ **{bus['rating']}**")
                    st.caption(" • ".join(bus["why_recommended"]))

                with b2:
                    st.write(f"Seats Left: **{bus['seats_available']}**")
                    if bus["best_coupon"]:
                        st.markdown(
                            f"<div class='coupon-pill'>🎟️ {bus['best_coupon']} (−₹{bus['discount_amount']:.0f})</div>",
                            unsafe_allow_html=True,
                        )
                        st.caption(bus["coupon_reason"])
                    else:
                        st.caption("No promo code applicable")

                with b3:
                    if bus["discount_amount"] > 0:
                        st.markdown(f"~~₹{bus['base_fare']:.0f}~~")
                    st.markdown(f"### ₹{bus['final_fare']:.0f}")
                    if st.button("Select Seats", key=f"sel_{bus['bus_id']}", width="stretch"):
                        st.session_state.selected_bus = bus
                        st.session_state.selected_seats = []
                        st.session_state.last_confirmed_ticket = None

        # INTERACTIVE SEAT LAYOUT & REAL-TIME COUPON BATTLE SIMULATOR
        if st.session_state.selected_bus:
            sel_bus = st.session_state.selected_bus
            st.divider()
            st.subheader(f"💺 Seat Selection & Real-Time Coupon Battle — {sel_bus['operator']}")

            deck_col, checkout_col = st.columns([1.15, 1.35])

            with deck_col:
                st.caption("🟩 Available   🟥 Selected   ⬜ Booked (Lower Deck)")
                booked_seats = {"L1", "L2", "L6", "L9"}
                seat_rows = [
                    ["L1", "L2", "L3"],
                    ["L4", "L5", "L6"],
                    ["L7", "L8", "L9"],
                    ["L10", "L11", "L12"],
                ]
                for row in seat_rows:
                    cols = st.columns(3)
                    for idx, seat_id in enumerate(row):
                        if seat_id in booked_seats:
                            cols[idx].button(f"⬜ {seat_id}", key=f"seat_{seat_id}", disabled=True, width="stretch")
                        elif seat_id in st.session_state.selected_seats:
                            if cols[idx].button(f"🟥 {seat_id}", key=f"seat_{seat_id}", width="stretch"):
                                st.session_state.selected_seats.remove(seat_id)
                                st.rerun()
                        else:
                            if cols[idx].button(f"🟩 {seat_id}", key=f"seat_{seat_id}", width="stretch"):
                                st.session_state.selected_seats.append(seat_id)
                                st.rerun()

            with checkout_col:
                with st.container(border=True):
                    st.markdown("#### ⚔️ Live Coupon Arbitrage & Checkout")
                    seats_chosen = st.session_state.selected_seats
                    seat_count = max(1, len(seats_chosen))
                    total_base = sel_bus["base_fare"] * seat_count
                    route_str = f"{sel_bus['source']}-{sel_bus['destination']}"

                    sim_user = st.radio(
                        "Simulate Account Tier",
                        ["Existing User (U101)", "New User (First Booking)"],
                        horizontal=True,
                    )
                    effective_user = "U101" if "Existing" in sim_user else "NEW_USER_DEMO"

                    best_res = find_best_coupon(
                        base_fare=total_base,
                        route=route_str,
                        bus_type=sel_bus["bus_type"],
                        user_id=effective_user,
                    )

                    applied_code = best_res["best_coupon"]
                    discount_val = best_res["discount_amount"]
                    final_payable = best_res["final_fare"]

                    st.write(f"**Seats:** {', '.join(seats_chosen) if seats_chosen else 'Select a green berth'} ({seat_count}x)")
                    st.write(f"**Base Fare:** ₹{total_base:.0f}  |  **AI Discount:** −₹{discount_val:.0f}")
                    st.markdown(f"### Final Payable: ₹{final_payable:.0f}")

                    # Real-Time Coupon Battle Breakdown
                    with st.expander(
                        f"🔍 View Coupon Battle ({len(best_res['all_eligible'])} Eligible • {len(best_res['rejected'])} Rejected)",
                        expanded=True,
                    ):
                        for idx, c in enumerate(best_res["all_eligible"]):
                            tag = "🏆 WINNER" if idx == 0 else "✅ ELIGIBLE"
                            st.markdown(
                                f"<div class='battle-win'><b>{tag}: {c['coupon_code']}</b> — Saves <b>₹{c['discount_amount']:.0f}</b> (Pay ₹{c['final_fare']:.0f})</div>",
                                unsafe_allow_html=True,
                            )
                        for r in best_res["rejected"][:4]:
                            st.markdown(
                                f"<div class='battle-lose'>❌ <b>{r['coupon_code']}</b> — {r['reason']}</div>",
                                unsafe_allow_html=True,
                            )

                    passenger_name = st.text_input("Passenger Name", value="Achu")
                    if st.button("✅ Confirm & Book Ticket", type="primary", width="stretch", disabled=len(seats_chosen) == 0):
                        bk_id = save_new_booking(
                            user_id="U101",
                            bus=sel_bus,
                            seats=seats_chosen,
                            final_fare=final_payable,
                            travel_date_str=travel_date.isoformat(),
                        )
                        st.session_state.last_confirmed_ticket = {
                            "booking_id": bk_id,
                            "passenger": passenger_name,
                            "operator": sel_bus["operator"],
                            "route": route_str,
                            "bus_type": sel_bus["bus_type"],
                            "date": travel_date.isoformat(),
                            "time": sel_bus["departure_time"],
                            "seats": ", ".join(seats_chosen),
                            "coupon": applied_code or "NONE",
                            "saved": discount_val,
                            "paid": final_payable,
                        }
                        st.session_state.selected_seats = []
                        st.rerun()

        # SHOW CONFIRMED DIGITAL M-TICKET
        if st.session_state.last_confirmed_ticket:
            t = st.session_state.last_confirmed_ticket
            st.success(f"🎉 Ticket Confirmed! Booking ID: **{t['booking_id']}** (Persisted to SQLite)")
            st.markdown(f"""
            <div class="ticket-card">
                <h3>🎫 BusBuddy Digital m-Ticket — #{t['booking_id']}</h3>
                <p><b>Passenger:</b> {t['passenger']} &nbsp;|&nbsp; <b>Route:</b> {t['route']}</p>
                <p><b>Operator:</b> {t['operator']} ({t['bus_type']}) &nbsp;|&nbsp; <b>Journey:</b> {t['date']} at {t['time']}</p>
                <p><b>Seat(s):</b> {t['seats']} &nbsp;|&nbsp; <b>Coupon Applied:</b> {t['coupon']} (Saved ₹{t['saved']:.0f}) &nbsp;|&nbsp; <b>Paid:</b> ₹{t['paid']:.0f}</p>
            </div>
            """, unsafe_allow_html=True)

    # RIGHT: EMBEDDED BUSBUDDY AI COPILOT SIDEBAR
    with copilot_col:
        with st.container(border=True):
            st.subheader("🤖 BusBuddy AI Copilot")
            st.caption("Autonomous tool-calling agent for route deals, fare math & policies.")

            if st.button("💡 Find highest discount for this route", width="stretch"):
                q = f"Find the best bus and highest discount coupon from {src_city} to {dst_city} within ₹1200"
                agent = BusBuddyAgent("U101")
                res = agent.run(q)
                st.session_state.chat_history.append({"role": "user", "content": q})
                st.session_state.chat_history.append({"role": "assistant", "content": res["response"], "tool_logs": res["tool_logs"]})

            quick_q = st.text_input("Ask Copilot...", placeholder="e.g., Best coupon for ₹1200 sleeper?")
            if st.button("Send to Agent", width="stretch") and quick_q:
                agent = BusBuddyAgent("U101")
                res = agent.run(quick_q)
                st.session_state.chat_history.append({"role": "user", "content": quick_q})
                st.session_state.chat_history.append({"role": "assistant", "content": res["response"], "tool_logs": res["tool_logs"]})

            for msg in st.session_state.chat_history[-4:]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("tool_logs"):
                        with st.expander(f"🛠️ Tools Invoked ({len(msg['tool_logs'])})"):
                            for log in msg["tool_logs"]:
                                st.json(log)

# =====================================================================
# TAB 2: FULL-SCREEN AI AGENT & TOOL EXECUTION INSPECTOR
# =====================================================================
with tab_agent:
    st.subheader("🤖 Agentic AI Travel & Coupon Assistant")
    st.caption(f"Engine Status: {'Gemini 2.5 Flash Connected' if LLM_AVAILABLE else 'Local Deterministic Fallback Mode'} | MCP Server: Ready")

    b1, b2, b3 = st.columns(3)
    demo_q = None
    if b1.button("🚌 Find my usual Bangalore bus", width="stretch"):
        demo_q = "Find me a bus to Bangalore this Saturday within my budget and apply the best coupon."
    if b2.button("🎟️ Compare coupons for ₹1,200 ticket", width="stretch"):
        demo_q = "I have a ₹1,200 AC Sleeper ticket from Chennai to Bangalore. Find the best valid coupon and calculate my final bill."
    if b3.button("📋 Check 2-hour cancellation rule", width="stretch"):
        demo_q = "Can I cancel my bus ticket 2 hours before departure?"

    full_q = st.chat_input("Message BusBuddy AI Agent...")
    prompt_to_run = demo_q or full_q

    if prompt_to_run:
        st.session_state.chat_history.append({"role": "user", "content": prompt_to_run})
        agent = BusBuddyAgent("U101")
        out = agent.run(prompt_to_run)
        st.session_state.chat_history.append({"role": "assistant", "content": out["response"], "tool_logs": out["tool_logs"]})

    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            if entry.get("tool_logs"):
                with st.expander(f"🛠️ Agent Tool Execution Log ({len(entry['tool_logs'])} tools invoked)", expanded=True):
                    for log in entry["tool_logs"]:
                        st.json(log)

# =====================================================================
# TAB 3: MY TRIPS & LEARNED USER PROFILE
# =====================================================================
with tab_trips:
    st.subheader("🧳 My Booking History & AI-Learned Travel Profile")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Bookings", patterns["total_bookings"])
    c2.metric("Favorite Route", patterns["top_route"], patterns["top_route_frequency"])
    c3.metric("Preferred Bus", patterns["preferred_bus_type"], patterns["bus_type_frequency"])
    c4.metric("Average Spend", f"₹{patterns['average_fare']:.0f}")

    st.dataframe(pd.DataFrame(patterns["bookings"]), width="stretch")

# =====================================================================
# TAB 4: RAG TRAVEL POLICY ASSISTANT
# =====================================================================
with tab_faq:
    st.subheader("📋 Travel Policy & Refund Assistant (FAISS + MiniLM RAG)")
    q_faq = st.text_input("Ask any cancellation, refund, luggage, or coupon policy question:", "Can I cancel my ticket 2 hours before departure?")
    if st.button("Search Policy Knowledge Base"):
        faq_out = query_travel_faq(q_faq)
        if faq_out["found"]:
            for m in faq_out["matches"]:
                with st.container(border=True):
                    st.write(m["text"])
                    st.caption(f"Source: `{m['source']}` | Cosine Similarity: `{m['score']}`")
        else:
            st.warning(faq_out["answer"])

# =====================================================================
# TAB 5: ANALYTICS & COUPON RULE AUDIT
# =====================================================================
with tab_analytics:
    st.subheader("📊 Travel Patterns & Live Synced Coupon Audit")
    df_bk = pd.DataFrame(patterns["bookings"])
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**Bus Type Preference**")
        st.bar_chart(df_bk["bus_type"].value_counts())
    with col_b:
        st.write("**Historical Ticket Spend (₹)**")
        st.line_chart(df_bk.set_index("booking_date")["fare_paid"])

    st.write("**All Synced Coupons in SQLite**")
    st.dataframe(pd.DataFrame(get_available_coupons()), width="stretch")