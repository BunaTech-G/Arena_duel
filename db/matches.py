from db.match_repository import (
    ensure_player_exists_by_name,
    get_match_history_records,
    get_serializable_match_history_records,
    save_match_result,
)


def ensure_player_exists(username):
    return ensure_player_exists_by_name(username, allow_ai_names=True)


# ----------------------------------------------------
# VERSION ACTUELLE COMPATIBLE AVEC TON MODE 1v1 ACTUEL
# ----------------------------------------------------
def save_match(
    player1_name,
    player2_name,
    team_a_score,
    team_b_score,
    duration_seconds,
):
    payload = {
        "source_code": "LOCAL",
        "mode_code": "LOCAL_HUMAN",
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "duration_seconds": duration_seconds,
        "players": [
            {
                "name": player1_name,
                "team": "A",
                "individual_score": team_a_score,
                "control_mode": "human",
                "is_ai": False,
                "slot_number": 1,
            },
            {
                "name": player2_name,
                "team": "B",
                "individual_score": team_b_score,
                "control_mode": "human",
                "is_ai": False,
                "slot_number": 2,
            },
        ],
    }

    try:
        save_match_result(payload)
        return True, "Partie enregistree."
    except RuntimeError as error:
        return False, str(error)


# ----------------------------------------------------
# FUTURE VERSION POUR 2v2 / 3v3 / jusqu'à 6 joueurs
# ----------------------------------------------------
def save_team_match(
    players_data,
    team_a_score,
    team_b_score,
    duration_seconds,
):
    payload = {
        "source_code": "LOCAL",
        "team_a_score": team_a_score,
        "team_b_score": team_b_score,
        "duration_seconds": duration_seconds,
        "players": list(players_data or []),
    }

    try:
        save_match_result(payload)
        return True, "La chronique de la joute a ete archivee."
    except RuntimeError as error:
        return False, str(error)


def get_match_history():
    return get_match_history_records()


def get_serializable_match_history():
    return get_serializable_match_history_records()
