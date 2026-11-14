from busbuddy.database import init_db, get_connection


def test_database_initialization_and_seed():
    init_db(force_reseed=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    assert cursor.fetchone()[0] == 1

    cursor.execute("SELECT COUNT(*) FROM bookings")
    assert cursor.fetchone()[0] == 8

    cursor.execute("SELECT COUNT(*) FROM buses")
    assert cursor.fetchone()[0] >= 5

    cursor.execute("SELECT COUNT(*) FROM coupons")
    assert cursor.fetchone()[0] == 5

    conn.close()