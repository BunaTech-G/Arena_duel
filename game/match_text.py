from game.score_formatter import format_score_value


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
END_SCREEN_SUMMARY_LABEL = "Points d'équipe"
END_SCREEN_PLAYER_VALUE_LABEL = "Points"
END_SCREEN_PLAYER_NAME_LABEL = "Combattant"


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


def get_end_screen_name_label(team_size: int) -> str:
    if int(team_size or 0) == 1:
        return END_SCREEN_PLAYER_NAME_LABEL
    return "Combattants"


def _format_scoreline_value(value: int, score_format_mode: str) -> str:
    normalized_mode = str(score_format_mode or "raw").strip().lower()
    if normalized_mode in {
        "grouped",
        "compact",
        "short",
        "abbr",
        "abbreviated",
    }:
        return format_score_value(value, normalized_mode)
    return str(int(value))


def format_scoreline(
    team_a_score: int,
    team_b_score: int,
    *,
    label_style: str = "bastion",
    separator: str = "   |   ",
    score_format_mode: str = "raw",
) -> str:
    return (
        f"{get_team_label('A', label_style)} : "
        f"{_format_scoreline_value(team_a_score, score_format_mode)}"
        f"{separator}"
        f"{get_team_label('B', label_style)} : "
        f"{_format_scoreline_value(team_b_score, score_format_mode)}"
    )


def format_compact_scoreline(team_a_score: int, team_b_score: int) -> str:
    return format_scoreline(
        team_a_score,
        team_b_score,
        label_style="short",
        separator=" - ",
        score_format_mode="compact",
    )


def build_scoreline_candidates(
    team_a_score: int,
    team_b_score: int,
) -> list[str]:
    return [
        format_scoreline(
            team_a_score,
            team_b_score,
            label_style="bastion",
            separator="   |   ",
            score_format_mode="grouped",
        ),
        format_scoreline(
            team_a_score,
            team_b_score,
            label_style="short",
            separator="   |   ",
            score_format_mode="grouped",
        ),
        format_scoreline(
            team_a_score,
            team_b_score,
            label_style="short",
            separator="  |  ",
            score_format_mode="compact",
        ),
    ]


def format_hud_text(
    team_a_score: int,
    team_b_score: int,
    remaining_time: int,
) -> str:
    return (
        f"{format_scoreline(team_a_score, team_b_score, label_style='short')}"
        f"   |   Sablier : {remaining_time}s"
    )


def format_team_assignment(slot: int, team_code: str | None) -> str:
    return f"Combattant assigné à l'emplacement {slot} · {get_team_label(team_code)}"


def format_roster_entry(
    slot: int, name: str, team_code: str | None, ready: bool
) -> str:
    readiness = "prêt" if ready else "en attente"
    return f"Emplacement {slot} · {name} · {get_team_label(team_code)} · {readiness}"
