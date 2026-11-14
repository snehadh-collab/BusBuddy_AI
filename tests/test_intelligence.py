from busbuddy.database import init_db
from busbuddy.coupon_engine import find_best_coupon
from busbuddy.recommendations import get_user_profile_and_patterns, recommend_buses


def setup_module():
    init_db(force_reseed=True)


def test_competing_coupons_and_cap():
    # Base fare 1200 on Chennai-Bangalore AC Sleeper:
    # BLR200 gives 20% = 240 -> capped at 200 -> final 1000
    # SLEEPER15 gives 15% = 180 -> final 1020
    # SAVE10 gives 10% = 120 -> final 1080
    result = find_best_coupon(base_fare=1200.0, route="Chennai-Bangalore", bus_type="AC Sleeper", user_id="U101")
    assert result["best_coupon"] == "BLR200"
    assert result["discount_amount"] == 200.0
    assert result["final_fare"] == 1000.0


def test_route_restriction_excludes_blr200():
    # On Chennai-Coimbatore AC Sleeper (1100), BLR200 shouldn't apply; SLEEPER15 (165 off) should win
    result = find_best_coupon(base_fare=1100.0, route="Chennai-Coimbatore", bus_type="AC Sleeper", user_id="U101")
    assert result["best_coupon"] == "SLEEPER15"
    assert result["discount_amount"] == 165.0
    assert result["final_fare"] == 935.0


def test_min_amount_not_reached():
    # Fare 400 is below every coupon's minimum booking amount
    result = find_best_coupon(base_fare=400.0, route="Chennai-Bangalore", bus_type="AC Seater", user_id="U101")
    assert result["best_coupon"] is None
    assert result["final_fare"] == 400.0


def test_personalized_patterns_and_recommendations():
    patterns = get_user_profile_and_patterns("U101")
    assert patterns["top_route"] == "Chennai-Bangalore"
    assert patterns["preferred_bus_type"] == "AC Sleeper"

    recs = recommend_buses(user_id="U101")
    top_pick = recs["recommendations"][0]
    assert top_pick["bus_type"] == "AC Sleeper"
    assert top_pick["best_coupon"] == "BLR200"
    assert top_pick["final_fare"] < top_pick["base_fare"]