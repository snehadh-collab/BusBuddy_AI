from datetime import date
from typing import Dict, List, Optional
from busbuddy.database import get_connection


def get_available_coupons() -> List[Dict]:
    """Fetch all coupons from SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM coupons")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def check_coupon_eligibility(
    coupon: Dict,
    base_fare: float,
    route: str,
    bus_type: str,
    is_first_time_user: bool = False,
    reference_date: Optional[date] = None,
) -> Dict:
    """Validate a single coupon against all business rules."""
    today = reference_date or date.today()
    expiry = date.fromisoformat(coupon["expiry_date"])

    if expiry < today:
        return {"eligible": False, "reason": f"Expired on {coupon['expiry_date']}"}

    if base_fare < coupon["min_booking_amount"]:
        return {
            "eligible": False,
            "reason": f"Minimum booking ₹{coupon['min_booking_amount']:.0f} required (current ₹{base_fare:.0f})",
        }

    if coupon["eligible_route"] != "ALL" and coupon["eligible_route"].lower() != route.lower():
        return {
            "eligible": False,
            "reason": f"Valid only on {coupon['eligible_route']} route",
        }

    if coupon["eligible_bus_type"] != "ALL" and coupon["eligible_bus_type"].lower() != bus_type.lower():
        return {
            "eligible": False,
            "reason": f"Valid only for {coupon['eligible_bus_type']} buses",
        }

    if coupon["first_time_only"] == 1 and not is_first_time_user:
        return {
            "eligible": False,
            "reason": "Valid only for first-time users",
        }

    return {"eligible": True, "reason": "All eligibility conditions satisfied"}


def calculate_discount(coupon: Dict, base_fare: float) -> float:
    """Calculate exact discount respecting percentage and max_discount cap."""
    raw_discount = (base_fare * coupon["discount_percent"]) / 100.0
    return round(min(raw_discount, coupon["max_discount"]), 2)


def calculate_final_fare(base_fare: float, discount_amount: float) -> float:
    """Return final payable fare after discount."""
    return round(max(0.0, base_fare - discount_amount), 2)


def find_best_coupon(
    base_fare: float,
    route: str,
    bus_type: str,
    user_id: str = "U101",
    reference_date: Optional[date] = None,
) -> Dict:
    """Evaluate all coupons, compare eligible savings, and select the highest-saving valid coupon."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_first_time_user FROM users WHERE user_id = ?", (user_id,))
    user_row = cursor.fetchone()
    conn.close()

    is_first_time = bool(user_row["is_first_time_user"]) if user_row else False
    all_coupons = get_available_coupons()

    eligible_options = []
    rejected_options = []

    for coupon in all_coupons:
        status = check_coupon_eligibility(
            coupon=coupon,
            base_fare=base_fare,
            route=route,
            bus_type=bus_type,
            is_first_time_user=is_first_time,
            reference_date=reference_date,
        )
        if status["eligible"]:
            discount = calculate_discount(coupon, base_fare)
            final_fare = calculate_final_fare(base_fare, discount)
            eligible_options.append({
                "coupon_code": coupon["coupon_code"],
                "description": coupon["description"],
                "discount_amount": discount,
                "final_fare": final_fare,
                "reason": status["reason"],
            })
        else:
            rejected_options.append({
                "coupon_code": coupon["coupon_code"],
                "reason": status["reason"],
            })

    # Sort eligible coupons by highest savings first
    eligible_options.sort(key=lambda x: x["discount_amount"], reverse=True)

    if not eligible_options:
        return {
            "original_fare": base_fare,
            "best_coupon": None,
            "discount_amount": 0.0,
            "final_fare": base_fare,
            "selection_reason": "No eligible coupons matched this booking.",
            "all_eligible": [],
            "rejected": rejected_options,
        }

    winner = eligible_options[0]
    runner_up_note = ""
    if len(eligible_options) > 1:
        runner_up = eligible_options[1]
        runner_up_note = (
            f" Beats {runner_up['coupon_code']} (₹{runner_up['discount_amount']:.0f} off) "
            f"by saving ₹{winner['discount_amount'] - runner_up['discount_amount']:.0f} more."
        )

    return {
        "original_fare": base_fare,
        "best_coupon": winner["coupon_code"],
        "discount_amount": winner["discount_amount"],
        "final_fare": winner["final_fare"],
        "selection_reason": f"{winner['description']}.{runner_up_note}",
        "all_eligible": eligible_options,
        "rejected": rejected_options,
    }