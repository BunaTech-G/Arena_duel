import mariadb


def get_connection():
    return mariadb.connect(
        host="localhost",
        port=3306,
        user="root",
        password="",
        database="arena_duel_v2_db"
    )


def test_connection():
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False