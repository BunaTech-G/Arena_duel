TEAM_LABELS = {
    "A": {
        "bastion": "Bastion braise",
        "camp": "camp braise",
        "short": "Braise",
    },
    "B": {
        "bastion": "Bastion azur",
        "camp": "camp azur",
        "short": "Azur",
    },
}

DRAW_LABEL = "Joute à égalité"


def get_team_label(team_code: str | None, style: str = "bastion") -> str:
    team_key = str(team_code or "").upper()
    label_set = TEAM_LABELS.get(team_key)

    if label_set is None:
        if style == "camp":
            return f"camp {team_key or '?'}"
        if style == "short":
            return team_key or "?"
        return f"Camp {team_key or '?'}"

    return label_set.get(style, label_set["bastion"])


def get_winner_team(team_a_score: int, team_b_score: int) -> str | None:
    if team_a_score > team_b_score:
        return "A"
    if team_b_score > team_a_score:
        return "B"
    return None


def format_winner_text(winner_team: str | None) -> str:
    if winner_team is None or str(winner_team).upper() == "DRAW":
        return DRAW_LABEL
    return f"Victoire du {get_team_label(winner_team)}"


def format_scoreline(
    team_a_score: int,
    team_b_score: int,
    *,
    label_style: str = "bastion",
    separator: str = "   |   ",
) -> str:
    return (
        f"{get_team_label('A', label_style)} : {team_a_score}"
        f"{separator}"
        f"{get_team_label('B', label_style)} : {team_b_score}"
    )


def format_compact_scoreline(team_a_score: int, team_b_score: int) -> str:
    return (
        f"{get_team_label('A', 'short')} {team_a_score}"
        f" - "
        f"{team_b_score} {get_team_label('B', 'short')}"
    )


def format_hud_text(team_a_score: int, team_b_score: int, remaining_time: int) -> str:
    return (
        f"{format_scoreline(team_a_score, team_b_score, label_style='short')}"
        f"   |   Sablier : {remaining_time}s"
    )


def format_team_assignment(slot: int, team_code: str | None) -> str:
    return f"Combattant assigné à l'emplacement {slot} · {get_team_label(team_code)}"


def format_roster_entry(slot: int, name: str, team_code: str | None, ready: bool) -> str:
    readiness = "prêt" if ready else "en attente"
    return f"Emplacement {slot} · {name} · {get_team_label(team_code)} · {readiness}"