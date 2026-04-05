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
        return False, "Le pseudo est vide."

    conn = get_connection()
    if not conn:
        return False, "Connexion base impossible."

    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO players (username) VALUES (?)", (username,))
        conn.commit()
        conn.close()
        return True, f"Joueur '{username}' créé."
    except mariadb.IntegrityError:
        conn.close()
        return False, "Ce pseudo existe déjà."
    except mariadb.Error as e:
        conn.close()
        return False, f"Erreur MariaDB : {e}"