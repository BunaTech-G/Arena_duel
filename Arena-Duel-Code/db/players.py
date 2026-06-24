import mariadb

from db import demo_store
from db.database import get_connection
from game.control_models import is_ai_name


def get_player_registry_snapshot():
    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.get_player_registry_snapshot()
        return False, []

    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username
        FROM players
        WHERE username NOT LIKE '[IA] %'
        ORDER BY username
        """
    )
    rows = cur.fetchall()
    conn.close()
    return True, rows


def get_all_players():
    _available, rows = get_player_registry_snapshot()
    return rows


def get_player_by_username(username):
    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.get_player_by_username(username)
        return None

    cur = conn.cursor()
    cur.execute(
        "SELECT id, username FROM players WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def create_player(username):
    username = (username or "").strip()

    if not username:
        return False, "Choisis un nom avant d'enrôler un combattant."

    if is_ai_name(username):
        return (
            False,
            "Le préfixe [IA] est réservé aux adversaires contrôlés par "
            "l'ordinateur.",
        )

    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.create_player(username)
        return False, "Le sanctuaire des chroniques est indisponible."

    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO players (username) VALUES (?)", (username,))
        conn.commit()
        conn.close()
        return (
            True,
            f"Le combattant '{username}' rejoint le registre du bastion.",
        )
    except mariadb.IntegrityError:
        conn.close()
        return False, "Ce nom de combattant figure déjà dans le registre."
    except mariadb.Error as e:
        conn.close()
        return False, f"MariaDB a refusé l'enrôlement : {e}"
