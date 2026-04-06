import mariadb
from db.database import get_connection
from game.match_text import get_team_label


def ensure_player_exists(username):
    username = (username or "").strip()

    if not username:
        return None

    conn = get_connection()
    if not conn:
        return None

    cur = conn.cursor()

    # Cherche d'abord le joueur
    cur.execute("SELECT id FROM players WHERE username = ?", (username,))
    row = cur.fetchone()

    if row:
        conn.close()
        return row[0]

    # Sinon on le crée
    try:
        cur.execute("INSERT INTO players (username) VALUES (?)", (username,))
        conn.commit()
        player_id = cur.lastrowid
        conn.close()
        return player_id
    except mariadb.Error as e:
        print(f"Erreur MariaDB création joueur : {e}")
        conn.close()
        return None


# ----------------------------------------------------
# VERSION ACTUELLE COMPATIBLE AVEC TON MODE 1v1 ACTUEL
# ----------------------------------------------------
def save_match(player1_name, player2_name, team_a_score, team_b_score, duration_seconds):
    """
    Fonction compatible avec le système actuel :
    - joueur 1 = équipe A
    - joueur 2 = équipe B
    """
    p1_id = ensure_player_exists(player1_name)
    p2_id = ensure_player_exists(player2_name)

    if not p1_id or not p2_id:
        return False, "Impossible de créer ou retrouver les joueurs en base."

    winner_team = None
    if team_a_score > team_b_score:
        winner_team = "A"
    elif team_b_score > team_a_score:
        winner_team = "B"

    conn = get_connection()
    if not conn:
        return False, "Le sanctuaire des chroniques est indisponible."

    cur = conn.cursor()

    try:
        # 1) insertion du match
        cur.execute(
            """
            INSERT INTO matches (
                team_a_score, team_b_score, winner_team, duration_seconds
            )
            VALUES (?, ?, ?, ?)
            """,
            (team_a_score, team_b_score, winner_team, duration_seconds),
        )
        conn.commit()
        match_id = cur.lastrowid

        # 2) insertion des joueurs du match
        cur.execute(
            """
            INSERT INTO match_players (match_id, player_id, team_code, individual_score)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, p1_id, "A", team_a_score),
        )

        cur.execute(
            """
            INSERT INTO match_players (match_id, player_id, team_code, individual_score)
            VALUES (?, ?, ?, ?)
            """,
            (match_id, p2_id, "B", team_b_score),
        )

        conn.commit()
        conn.close()
        return True, "Partie enregistrée."
    except mariadb.Error as e:
        conn.close()
        return False, f"Erreur MariaDB : {e}"


# ----------------------------------------------------
# FUTURE VERSION POUR 2v2 / 3v3 / jusqu'à 6 joueurs
# ----------------------------------------------------
def save_team_match(players_data, team_a_score, team_b_score, duration_seconds):
    """
    players_data = [
        {"name": "Ali", "team": "A", "individual_score": 3},
        {"name": "Lina", "team": "B", "individual_score": 2},
        ...
    ]
    """

    conn = get_connection()
    if not conn:
        return False, "Connexion base impossible."

    cur = conn.cursor()

    try:
        winner_team = None
        if team_a_score > team_b_score:
            winner_team = "A"
        elif team_b_score > team_a_score:
            winner_team = "B"

        # 1) insertion du match global
        cur.execute(
            """
            INSERT INTO matches (
                team_a_score, team_b_score, winner_team, duration_seconds
            )
            VALUES (?, ?, ?, ?)
            """,
            (team_a_score, team_b_score, winner_team, duration_seconds),
        )
        conn.commit()
        match_id = cur.lastrowid

        # 2) insertion des joueurs participants
        for player in players_data:
            player_name = player.get("name", "").strip()
            team_code = player.get("team", "").strip().upper()
            individual_score = int(player.get("individual_score", 0))

            player_id = ensure_player_exists(player_name)
            if not player_id:
                continue

            cur.execute(
                """
                INSERT INTO match_players (
                    match_id, player_id, team_code, individual_score
                )
                VALUES (?, ?, ?, ?)
                """,
                (match_id, player_id, team_code, individual_score),
            )

        conn.commit()
        conn.close()
        return True, "La chronique de la joute a été archivée."
    except mariadb.Error as e:
        conn.close()
        return False, f"MariaDB n'a pas pu archiver la joute : {e}"


def get_match_history():
    """
    Retourne une liste de tuples compatibles avec l'historique actuel :
    (
        match_id,
        team_a_players,
        team_b_players,
        winner_display,
        team_a_score,
        team_b_score,
        duration_seconds,
        played_at
    )
    """
    conn = get_connection()
    if not conn:
        return []

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            m.id,
            m.team_a_score,
            m.team_b_score,
            m.winner_team,
            m.duration_seconds,
            m.played_at,
            p.username,
            mp.team_code
        FROM matches m
        JOIN match_players mp ON m.id = mp.match_id
        JOIN players p ON mp.player_id = p.id
        ORDER BY m.played_at DESC, m.id DESC
        """
    )

    rows = cur.fetchall()
    conn.close()

    if not rows:
        return []

    matches_map = {}

    for row in rows:
        match_id, team_a_score, team_b_score, winner_team, duration_seconds, played_at, username, team_code = row

        if match_id not in matches_map:
            matches_map[match_id] = {
                "team_a_score": team_a_score,
                "team_b_score": team_b_score,
                "winner_team": winner_team,
                "duration_seconds": duration_seconds,
                "played_at": played_at,
                "team_a_players": [],
                "team_b_players": [],
            }

        if team_code == "A":
            matches_map[match_id]["team_a_players"].append(username)
        elif team_code == "B":
            matches_map[match_id]["team_b_players"].append(username)

    result = []

    for match_id, data in matches_map.items():
        team_a_players = ", ".join(data["team_a_players"])
        team_b_players = ", ".join(data["team_b_players"])

        if data["winner_team"] == "A":
            winner_display = get_team_label("A")
        elif data["winner_team"] == "B":
            winner_display = get_team_label("B")
        else:
            winner_display = None

        result.append(
            (
                match_id,
                team_a_players,
                team_b_players,
                winner_display,
                data["team_a_score"],
                data["team_b_score"],
                data["duration_seconds"],
                data["played_at"],
            )
        )

    # Tri final : plus récent d'abord
    result.sort(key=lambda x: x[7], reverse=True)
    return result


def get_serializable_match_history():
    rows = get_match_history()
    serialized_rows = []

    for row in rows:
        row_data = list(row)
        if len(row_data) >= 8 and row_data[7] is not None:
            row_data[7] = str(row_data[7])
        serialized_rows.append(row_data)

    return serialized_rows
