import mariadb
from db.database import get_connection


def get_all_players():
    conn = get_connection()
    if not conn:
        return []

    cur = conn.cursor()
    cur.execute("SELECT id, username FROM players ORDER BY username")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_player_by_username(username):
    conn = get_connection()
    if not conn:
        return None

    cur = conn.cursor()
    cur.execute("SELECT id, username FROM players WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_player(username):
    username = (username or "").strip()

    if not username:
        return False, "Choisis un nom avant d'enrôler un combattant."

    conn = get_connection()
    if not conn:
        return False, "Le sanctuaire des chroniques est indisponible."

    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO players (username) VALUES (?)", (username,))
        conn.commit()
        conn.close()
        return True, f"Le combattant '{username}' rejoint le registre du bastion."
    except mariadb.IntegrityError:
        conn.close()
        return False, "Ce nom de combattant figure déjà dans le registre."
    except mariadb.Error as e:
        conn.close()
        return False, f"MariaDB a refusé l'enrôlement : {e}"