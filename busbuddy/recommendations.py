from collections import Counter
from typing import Dict, List, Optional
from busbuddy.database import get_connection
from busbuddy.coupon_engine import find_best_coupon


def get_user_profile_and_patterns(user_id: str = "U101") -> Dict:
    """Analyze a user's historical bookings to extract travel habits and preferences."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return {"error": f"User {user_id} not found"}

    cursor.execute("SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC", (user_id,))
    bookings = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not bookings:
        return {
            "user": dict(user),
            "total_bookings": 0,
            "top_route": None,
            "preferred_bus_type": None,
            "preferred_slot": None,
            "average_fare": user["preferred_budget"],
            "bookings": [],
        }

    routes = Counter(f"{b['source']}-{b['destination']}" for b in bookings)
    bus_types = Counter(b["bus_type"] for b in bookings)
    slots = Counter(b["departure_slot"] for b in bookings)
    avg_fare = round(sum(b["fare_paid"] for b in bookings) / len(bookings), 2)

    top_route, top_route_count = routes.most_common(1)[0]
    top_bus_type, top_bus_count = bus_types.most_common(1)[0]
    top_slot, top_slot_count = slots.most_common(1)[0]

    return {
        "user": dict(user),
        "total_bookings": len(bookings),
        "top_route": top_route,
        "top_route_frequency": f"{top_route_count}/{len(bookings)} trips",
        "preferred_bus_type": top_bus_type,
        "bus_type_frequency": f"{top_bus_count}/{len(bookings)} trips",
        "preferred_slot": top_slot,
        "slot_frequency": f"{top_slot_count}/{len(bookings)} trips",
        "average_fare": avg_fare,
        "bookings": bookings,
    }


def search_buses(
    source: str,
    destination: str,
    max_budget: Optional[float] = None,
    bus_type: Optional[str] = None,
) -> List[Dict]:
    """Query simulated bus inventory matching route and optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM buses WHERE LOWER(source) = LOWER(?) AND LOWER(destination) = LOWER(?)"
    params: list = [source.strip(), destination.strip()]

    if max_budget is not None:
        query += " AND base_fare <= ?"
        params.append(max_budget)

    if bus_type and bus_type.upper() != "ALL":
        query += " AND LOWER(bus_type) = LOWER(?)"
        params.append(bus_type.strip())

    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def recommend_buses(
    user_id: str = "U101",
    source: Optional[str] = None,
    destination: Optional[str] = None,
    max_budget: Optional[float] = None,
) -> Dict:
    """Recommend buses scored by historical preferences + automatically attach best coupon savings."""
    patterns = get_user_profile_and_patterns(user_id)
    if "error" in patterns:
        return patterns

    # Default to user's most frequent route if none specified
    if not source or not destination:
        if patterns["top_route"]:
            source, destination = patterns["top_route"].split("-")
        else:
            source, destination = "Chennai", "Bangalore"

    budget_limit = max_budget or patterns["user"]["preferred_budget"]
    candidates = search_buses(source, destination)

    scored_recommendations = []
    for bus in candidates:
        route_str = f"{bus['source']}-{bus['destination']}"
        coupon_info = find_best_coupon(
            base_fare=bus["base_fare"],
            route=route_str,
            bus_type=bus["bus_type"],
            user_id=user_id,
        )
        final_fare = coupon_info["final_fare"]

        score = 0
        reasons = []

        if bus["bus_type"] == patterns["preferred_bus_type"]:
            score += 40
            reasons.append(f"Matches your preferred {bus['bus_type']} ({patterns['bus_type_frequency']})")

        if bus["departure_slot"] == patterns["preferred_slot"]:
            score += 25
            reasons.append(f"Matches your usual {bus['departure_slot']} departure habit")

        if final_fare <= budget_limit:
            score += 25
            reasons.append(f"Final fare ₹{final_fare:.0f} fits within your ₹{budget_limit:.0f} budget")
        else:
            reasons.append(f"Slightly above your ₹{budget_limit:.0f} budget (₹{final_fare:.0f} after coupon)")

        score += int(bus["rating"] * 2)

        scored_recommendations.append({
            **bus,
            "match_score": score,
            "best_coupon": coupon_info["best_coupon"],
            "discount_amount": coupon_info["discount_amount"],
            "final_fare": final_fare,
            "coupon_reason": coupon_info["selection_reason"],
            "why_recommended": reasons,
        })

    scored_recommendations.sort(key=lambda x: (x["match_score"], -x["final_fare"]), reverse=True)

    return {
        "user_patterns": {
            "top_route": patterns["top_route"],
            "preferred_bus_type": patterns["preferred_bus_type"],
            "bus_type_frequency": patterns.get("bus_type_frequency"),
            "preferred_slot": patterns["preferred_slot"],
            "average_fare": patterns["average_fare"],
        },
        "route": f"{source}-{destination}",
        "recommendations": scored_recommendations,
    }