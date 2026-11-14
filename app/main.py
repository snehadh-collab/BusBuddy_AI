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
    search_buses,
    recommend_buses,
)
from busbuddy.coupon_engine import get_available_coupons, find_best_coupon
from busbuddy.rag.retriever import query_travel_faq
from busbuddy.agent import BusBuddyAgent

st.set_page_config(
    page_title="BusBuddy AI – Smart Bus Ticket Booking",
    page_icon="🚌",
    layout="wide",
)

# RedBus-inspired Coral/Navy + AI Copilot Styling
st.markdown("""
<style>
    .booking-header {
        background: linear-gradient(120deg, #D84E55 0%, #991B1B 55%, #1E1B4B 100%);
        padding: 1.4rem 2rem;
        border-radius: 14px;
        color: white;
        margin-bottom: 1.2rem;
    }
    .booking-header h1 { color: white; margin: 0; font-size: 1.9rem; }
    .booking-header p { color: #FEE2E2; margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .ai-nudge {
        background: linear-gradient(90deg, #EEF2FF 0%, #F5F3FF 100%);
        border-left: 5px solid #6D28D9;
        padding: 0.9rem 1.2rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        color: #1E1B4B;
    }
    .coupon-pill {
        background-color: #ECFDF5;
        border: 1px dashed #059669;
        color: #065F46;
        padding: 0.3rem 0.65rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .ticket-card {
        background: #FFFFFF;
        border: 2px solid #D84E55;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)

init_db()

# Session state for booking flow
if "selected_bus" not in st.session_state:
    st.session_state.selected_bus = None
if "selected_seats" not in st.session_state:
    st.session_state.selected_seats = []
if "last_confirmed_ticket" not in st.session_state:
    st.session_state.last_confirmed_ticket = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "search_src" not in st.session_state:
    st.session_state.search_src = "Chennai"
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

    # Reduce available seats in inventory
    new_seats = max(0, bus["seats_available"] - len(seats))
    cursor.execute("UPDATE buses SET seats_available = ? WHERE bus_id = ?", (new_seats, bus["bus_id"]))

    conn.commit()
    conn.close()
    return booking_id


# Top Navigation Tabs (Looks & feels like a real consumer booking portal)
st.markdown("""
<div class="booking-header">
    <h1>🚌 BusBuddy AI — Smart Bus Ticket Booking</h1>
    <p>Book bus tickets faster with Agentic AI personalization, interactive seat selection & automatic coupon savings</p>
</div>
""", unsafe_allow_html=True)

tab_book, tab_agent, tab_trips, tab_faq, tab_analytics = st.tabs([
    "🎫 Book Bus Tickets",
    "🤖 BusBuddy AI Agent",
    "🧳 My Trips & Profile",
    "📋 Travel Policies (RAG)",
    "📊 Spend & Route Insights",
])

patterns = get_user_profile_and_patterns("U101")

# =====================================================================
# TAB 1: REAL BUS TICKET BOOKING FLOW + EMBEDDED AI COPILOT
# =====================================================================
with tab_book:
    # Smart AI Habit Nudge Banner (What RedBus doesn't have!)
    st.markdown(f"""
    <div class="ai-nudge">
        <strong>✨ BusBuddy AI Habit Detection:</strong> Welcome back, <b>{patterns['user']['name']}</b>!
        You booked <b>{patterns['top_route']}</b> ({patterns['top_route_frequency']}) mostly in
        <b>{patterns['preferred_bus_type']}</b> ({patterns['bus_type_frequency']}) during <b>{patterns['preferred_slot']}</b> hours.
        Best promo codes are auto-applied to every bus below!
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
        if s5.button("⚡ AI Best Pick", use_container_width=True, type="primary"):
            st.session_state.search_dst = "Bangalore"
            recs = recommend_buses("U101", source="Chennai", destination="Bangalore")
            if recs["recommendations"]:
                st.session_state.selected_bus = recs["recommendations"][0]
                st.session_state.selected_seats = ["L4"]

    main_col, copilot_col = st.columns([2.2, 1])

    # LEFT: Available Buses + Seat Selection + Checkout
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
                    if st.button("Select Seats", key=f"sel_{bus['bus_id']}", use_container_width=True):
                        st.session_state.selected_bus = bus
                        st.session_state.selected_seats = []
                        st.session_state.last_confirmed_ticket = None

        # INTERACTIVE SEAT LAYOUT & CHECKOUT DRAWER
        if st.session_state.selected_bus:
            sel_bus = st.session_state.selected_bus
            st.divider()
            st.subheader(f"💺 Select Seats — {sel_bus['operator']} ({sel_bus['bus_type']})")

            deck_col, checkout_col = st.columns([1.3, 1.2])

            with deck_col:
                st.caption("🟩 Available   🟥 Selected   ⬜ Booked (Lower Deck Berth Map)")
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
                            cols[idx].button(f"⬜ {seat_id}", key=f"seat_{seat_id}", disabled=True, use_container_width=True)
                        elif seat_id in st.session_state.selected_seats:
                            if cols[idx].button(f"🟥 {seat_id}", key=f"seat_{seat_id}", use_container_width=True):
                                st.session_state.selected_seats.remove(seat_id)
                                st.rerun()
                        else:
                            if cols[idx].button(f"🟩 {seat_id}", key=f"seat_{seat_id}", use_container_width=True):
                                st.session_state.selected_seats.append(seat_id)
                                st.rerun()

            with checkout_col:
                with st.container(border=True):
                    st.markdown("#### 🧾 Smart Fare & Checkout")
                    seats_chosen = st.session_state.selected_seats
                    seat_count = max(1, len(seats_chosen))
                    total_base = sel_bus["base_fare"] * seat_count
                    route_str = f"{sel_bus['source']}-{sel_bus['destination']}"

                    # Allow manual coupon override OR AI auto-best coupon
                    all_codes = ["AUTO (AI Best)"] + [c["coupon_code"] for c in get_available_coupons()]
                    chosen_code = st.selectbox("Promo Code", all_codes)

                    best_res = find_best_coupon(
                        base_fare=total_base,
                        route=route_str,
                        bus_type=sel_bus["bus_type"],
                        user_id="U101",
                    )

                    if chosen_code != "AUTO (AI Best)":
                        # Check manual override against engine
                        manual_match = next((c for c in best_res["all_eligible"] if c["coupon_code"] == chosen_code), None)
                        if manual_match:
                            applied_code = manual_match["coupon_code"]
                            discount_val = manual_match["discount_amount"]
                            final_payable = manual_match["final_fare"]
                        else:
                            rej = next((r for r in best_res["rejected"] if r["coupon_code"] == chosen_code), None)
                            st.error(f"❌ {chosen_code}: {rej['reason'] if rej else 'Not eligible'}")
                            applied_code = None
                            discount_val = 0.0
                            final_payable = total_base
                    else:
                        applied_code = best_res["best_coupon"]
                        discount_val = best_res["discount_amount"]
                        final_payable = best_res["final_fare"]

                    st.write(f"**Selected Seats:** {', '.join(seats_chosen) if seats_chosen else 'None selected yet'}")
                    st.write(f"**Base Fare ({seat_count} seat):** ₹{total_base:.0f}")
                    st.write(f"**Coupon ({applied_code or 'None'}):** −₹{discount_val:.0f}")
                    st.markdown(f"### Total Payable: ₹{final_payable:.0f}")

                    passenger_name = st.text_input("Passenger Name", value="Achu")
                    if st.button("✅ Confirm & Book Ticket", type="primary", use_container_width=True, disabled=len(seats_chosen) == 0):
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
            st.success(f"🎉 Ticket Confirmed! Booking ID: **{t['booking_id']}** (Saved to SQLite Booking History)")
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
            st.caption("Ask me to find buses, compare coupons, or check policies while you book.")

            if st.button("💡 Suggest best offer for this route", use_container_width=True):
                q = f"Find the best bus and highest discount coupon from {src_city} to {dst_city} within ₹1200"
                agent = BusBuddyAgent("U101")
                res = agent.run(q)
                st.session_state.chat_history.append({"role": "user", "content": q})
                st.session_state.chat_history.append({"role": "assistant", "content": res["response"], "tool_logs": res["tool_logs"]})

            quick_q = st.text_input("Ask Copilot...", placeholder="e.g., Any coupon for ₹1200 sleeper?")
            if st.button("Send to Agent", use_container_width=True) and quick_q:
                agent = BusBuddyAgent("U101")
                res = agent.run(quick_q)
                st.session_state.chat_history.append({"role": "user", "content": quick_q})
                st.session_state.chat_history.append({"role": "assistant", "content": res["response"], "tool_logs": res["tool_logs"]})

            for msg in st.session_state.chat_history[-4:]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("tool_logs"):
                        with st.expander(f"🛠️ Tools Called ({len(msg['tool_logs'])})"):
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
    if b1.button("🚌 Find my usual Bangalore bus", use_container_width=True):
        demo_q = "Find me a bus to Bangalore this Saturday within my budget and apply the best coupon."
    if b2.button("🎟️ Compare coupons for ₹1,200 ticket", use_container_width=True):
        demo_q = "I have a ₹1,200 AC Sleeper ticket from Chennai to Bangalore. Find the best valid coupon and calculate my final bill."
    if b3.button("📋 Check 2-hour cancellation rule", use_container_width=True):
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

    st.dataframe(pd.DataFrame(patterns["bookings"]), use_container_width=True)

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
    st.subheader("📊 Travel Patterns & Coupon Database")
    df_bk = pd.DataFrame(patterns["bookings"])
    col_a, col_b = st.columns(2)
    with col_a:
        st.write("**Bus Type Preference**")
        st.bar_chart(df_bk["bus_type"].value_counts())
    with col_b:
        st.write("**Historical Ticket Spend (₹)**")
        st.line_chart(df_bk.set_index("booking_date")["fare_paid"])

    st.write("**Active & Expired Coupons in SQLite**")
    st.dataframe(pd.DataFrame(get_available_coupons()), use_container_width=True)