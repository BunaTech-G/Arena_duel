import mariadb

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "arena_duel_v2_db"
}


def get_connection():
    try:
        conn = mariadb.connect(**DB_CONFIG)
        return conn
    except mariadb.Error as e:
        print(f"Erreur connexion MariaDB : {e}")
        return None


def test_connection():
    conn = get_connection()
    if conn:
        print("Connexion MariaDB réussie.")
        conn.close()
        return True
    print("Connexion MariaDB échouée.")
    return False
