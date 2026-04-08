import mariadb

from db.database import get_connection


PLAYER_NAME_COLUMN = "username"


def _get_or_create_player_id(cursor, player_name: str) -> int:
    # chercher le joueur
    cursor.execute(
        f"SELECT id FROM players WHERE {PLAYER_NAME_COLUMN} = ?",
        (player_name,)
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    # sinon le créer
    cursor.execute(
        f"INSERT INTO players ({PLAYER_NAME_COLUMN}) VALUES (?)",
        (player_name,)
    )
    return cursor.lastrowid


def save_network_match_result(match_result: dict) -> int:
    conn = get_connection()
    if not conn:
        raise RuntimeError(
            "Le sanctuaire des chroniques LAN est indisponible."
        )

    cursor = conn.cursor()

    try:
        team_a_score = match_result.get("team_a_score", 0)
        team_b_score = match_result.get("team_b_score", 0)
        winner_team = match_result.get("winner_team", "DRAW")
        duration_seconds = match_result.get("duration_seconds", 60)

        cursor.execute(
            """
            INSERT INTO matches (
                team_a_score,
                team_b_score,
                winner_team,
                duration_seconds,
                played_at
            )
            VALUES (?, ?, ?, ?, NOW())
            """,
            (team_a_score, team_b_score, winner_team, duration_seconds),
        )
        match_id = cursor.lastrowid

        for player in match_result.get("players", []):
            player_name = player["name"]
            team_code = player["team"]
            individual_score = player["score"]

            player_id = _get_or_create_player_id(cursor, player_name)

            cursor.execute(
                """
                INSERT INTO match_players (
                    match_id,
                    player_id,
                    team_code,
                    individual_score
                )
                VALUES (?, ?, ?, ?)
                """,
                (match_id, player_id, team_code, individual_score),
            )

        conn.commit()
        return match_id

    except mariadb.Error:
        conn.rollback()
        raise

    finally:
        conn.close()
