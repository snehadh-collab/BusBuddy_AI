import sqlite3
from datetime import date, timedelta
from busbuddy.config import DATABASE_PATH, DATA_DIR


def get_connection():
    """Create and return a SQLite database connection with Row factory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reseed: bool = False):
    """Initialize tables and seed realistic sample data if empty."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            is_first_time_user INTEGER DEFAULT 0,
            preferred_budget REAL DEFAULT 1200.0
        )
    """)

    # 2. Past Bookings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            operator TEXT NOT NULL,
            bus_type TEXT NOT NULL,
            departure_slot TEXT NOT NULL,
            travel_day_type TEXT NOT NULL,
            fare_paid REAL NOT NULL,
            booking_date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # 3. Available Buses Table (Simulated Inventory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            bus_id TEXT PRIMARY KEY,
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            bus_type TEXT NOT NULL,
            departure_time TEXT NOT NULL,
            departure_slot TEXT NOT NULL,
            base_fare REAL NOT NULL,
            seats_available INTEGER NOT NULL,
            rating REAL NOT NULL
        )
    """)

    # 4. Coupons Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            coupon_code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            discount_percent REAL NOT NULL,
            max_discount REAL NOT NULL,
            min_booking_amount REAL NOT NULL,
            expiry_date TEXT NOT NULL,
            eligible_route TEXT DEFAULT 'ALL',
            eligible_bus_type TEXT DEFAULT 'ALL',
            first_time_only INTEGER DEFAULT 0
        )
    """)

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0 and not force_reseed:
        conn.close()
        return

    # Clear existing data if reseeding
    for table in ["bookings", "buses", "coupons", "users"]:
        cursor.execute(f"DELETE FROM {table}")

    # Seed Sample User (Frequent Chennai -> Bangalore traveler)
    cursor.execute("""
        INSERT INTO users (user_id, name, email, is_first_time_user, preferred_budget)
        VALUES ('U101', 'Achu', 'achu@veltech.edu.in', 0, 1200.0)
    """)

    # Seed 8 Past Bookings (7 AC Sleeper on Chennai -> Bangalore, mostly Night/Weekend)
    past_bookings = [
        ("BK001", "U101", "Chennai", "Bangalore", "IntrCity SmartBus", "AC Sleeper", "Night", "Weekend", 1150.0, "2026-08-08"),
        ("BK002", "U101", "Chennai", "Bangalore", "Parveen Travels", "AC Sleeper", "Night", "Weekend", 1100.0, "2026-08-22"),
        ("BK003", "U101", "Chennai", "Bangalore", "Zingbus Plus", "AC Sleeper", "Night", "Weekend", 1080.0, "2026-09-05"),
        ("BK004", "U101", "Chennai", "Bangalore", "NueGo Electric", "AC Seater", "Morning", "Weekday", 850.0, "2026-09-16"),
        ("BK005", "U101", "Chennai", "Bangalore", "KPN Travels", "AC Sleeper", "Night", "Weekend", 1120.0, "2026-10-03"),
        ("BK006", "U101", "Chennai", "Bangalore", "IntrCity SmartBus", "AC Sleeper", "Night", "Weekend", 1180.0, "2026-10-17"),
        ("BK007", "U101", "Chennai", "Bangalore", "Orange Tours", "AC Sleeper", "Night", "Weekday", 1090.0, "2026-10-28"),
        ("BK008", "U101", "Chennai", "Bangalore", "Parveen Travels", "AC Sleeper", "Night", "Weekend", 1150.0, "2026-11-07"),
    ]
    cursor.executemany("""
        INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, past_bookings)

    # Seed Simulated Bus Inventory
    buses = [
        ("BUS101", "IntrCity SmartBus", "Chennai", "Bangalore", "AC Sleeper", "10:30 PM", "Night", 1200.0, 12, 4.7),
        ("BUS102", "Parveen Travels", "Chennai", "Bangalore", "AC Sleeper", "11:00 PM", "Night", 1150.0, 8, 4.5),
        ("BUS103", "NueGo Electric", "Chennai", "Bangalore", "AC Seater", "07:00 AM", "Morning", 850.0, 18, 4.6),
        ("BUS104", "SRM Transports", "Chennai", "Bangalore", "Non-AC Sleeper", "09:45 PM", "Night", 750.0, 15, 4.1),
        ("BUS105", "YBM Travels", "Chennai", "Bangalore", "AC Sleeper", "10:15 PM", "Night", 1450.0, 6, 4.8),
        ("BUS106", "KPN Travels", "Chennai", "Coimbatore", "AC Sleeper", "10:00 PM", "Night", 1100.0, 10, 4.4),
        ("BUS107", "Orange Tours", "Chennai", "Hyderabad", "AC Sleeper", "08:30 PM", "Night", 1600.0, 9, 4.6),
    ]
    cursor.executemany("""
        INSERT INTO buses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, buses)

    # Seed Coupons (Covering valid, capped, route-specific, first-time, and expired cases)
    today = date.today()
    valid_future = (today + timedelta(days=30)).isoformat()
    expired_past = (today - timedelta(days=5)).isoformat()

    coupons = [
        ("SAVE10", "10% off up to ₹150 on bookings above ₹800", 10.0, 150.0, 800.0, valid_future, "ALL", "ALL", 0),
        ("BLR200", "Flat 20% off up to ₹200 on Chennai-Bangalore AC Sleeper", 20.0, 200.0, 1000.0, valid_future, "Chennai-Bangalore", "AC Sleeper", 0),
        ("SLEEPER15", "15% off up to ₹180 on any AC Sleeper bus", 15.0, 180.0, 900.0, valid_future, "ALL", "AC Sleeper", 0),
        ("FIRST50", "50% off up to ₹300 for first-time users", 50.0, 300.0, 500.0, valid_future, "ALL", "ALL", 1),
        ("EXPIRED25", "25% off up to ₹250 (Expired Promo)", 25.0, 250.0, 500.0, expired_past, "ALL", "ALL", 0),
    ]
    cursor.executemany("""
        INSERT INTO coupons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, coupons)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db(force_reseed=True)
    print(f"Database initialized and seeded at: {DATABASE_PATH}")