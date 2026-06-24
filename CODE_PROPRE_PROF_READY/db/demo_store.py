from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from game.control_models import is_ai_name
from game.match_text import get_team_label
from runtime_utils import (
    is_runtime_flag_enabled,
    load_runtime_config,
    runtime_user_file_path,
)


DEMO_STORE_FILENAME = "arena_duel_demo_state.json"
DEFAULT_DEMO_PLAYERS = (
    "Aegis",
    "Selene",
    "Orion",
    "Nyx",
    "Kael",
    "Iris",
)


def is_demo_storage_enabled() -> bool:
    return is_runtime_flag_enabled("demo_local_storage_enabled", False)


def should_force_demo_storage() -> bool:
    return is_runtime_flag_enabled("demo_local_storage_force", False)


def get_demo_store_path() -> Path:
    return Path(runtime_user_file_path(DEMO_STORE_FILENAME))


def get_player_registry_snapshot() -> tuple[bool, list[tuple[int, str]]]:
    state = _load_state()
    rows = [
        (int(player["id"]), str(player["username"]))
        for player in state["players"]
        if not is_ai_name(player["username"])
    ]
    rows.sort(key=lambda item: item[1].casefold())
    return True, rows


def get_player_by_username(username: str):
    clean_username = str(username or "").strip()
    if not clean_username:
        return None

    state = _load_state()
    for player in state["players"]:
        if str(player["username"]).casefold() == clean_username.casefold():
            return int(player["id"]), str(player["username"])
    return None


def create_player(username: str):
    clean_username = str(username or "").strip()

    if not clean_username:
        return False, "Choisis un nom avant d'enroler un combattant."

    if is_ai_name(clean_username):
        return (
            False,
            "Le prefixe [IA] est reserve aux adversaires controles par "
            "l'ordinateur.",
        )

    state = _load_state()
    existing_player = _find_player(state, clean_username)
    if existing_player is not None:
        return False, "Ce nom de combattant figure deja dans le registre."

    _append_player(state, clean_username)
    _save_state(state)
    return (
        True,
        f"Le combattant '{clean_username}' rejoint le registre du bastion.",
    )


def ensure_player_exists_by_name(
    username: str,
    *,
    allow_ai_names: bool = False,
):
    clean_username = str(username or "").strip()
    if not clean_username:
        return None
    if is_ai_name(clean_username) and not allow_ai_names:
        return None

    state = _load_state()
    existing_player = _find_player(state, clean_username)
    if existing_player is not None:
        return int(existing_player["id"])

    player_id = _append_player(state, clean_username)
    _save_state(state)
    return player_id


def save_match_result(match_result: dict) -> int:
    state = _load_state()
    participants = _normalize_participants(match_result)

    for participant in participants:
        _ensure_player_exists_in_state(
            state,
            participant["name"],
            allow_ai_names=True,
        )

    next_match_id = max(
        (_coerce_int(row.get("match_id"), 0) for row in state["matches"]),
        default=0,
    ) + 1

    winner_team = _normalize_winner_team(match_result.get("winner_team"))
    ai_participants = sum(1 for player in participants if player["is_ai"])
    team_a_players = ", ".join(
        player["name"]
        for player in participants
        if player["team_code"] == "A"
    ) or "-"
    team_b_players = ", ".join(
        player["name"]
        for player in participants
        if player["team_code"] == "B"
    ) or "-"
    arena_code = str(
        match_result.get("arena_code")
        or match_result.get("map_id")
        or "forgotten_sanctum"
    ).strip() or "forgotten_sanctum"
    played_at = _serialize_datetime(
        match_result.get("finished_at")
        or match_result.get("played_at")
        or datetime.now()
    )

    record = {
        "match_id": next_match_id,
        "arena_code": arena_code,
        "arena_label": arena_code.replace("_", " ").title(),
        "mode_code": str(
            match_result.get("mode_code")
            or ("LOCAL_AI" if ai_participants > 0 else "LOCAL_HUMAN")
        ).upper(),
        "source_code": str(
            match_result.get("source_code") or "LOCAL"
        ).upper(),
        "status_code": str(
            match_result.get("status_code") or "COMPLETED"
        ).upper(),
        "team_a_players": team_a_players,
        "team_b_players": team_b_players,
        "winner_team": winner_team,
        "winner_display": _winner_display(winner_team),
        "team_a_score": _coerce_int(match_result.get("team_a_score"), 0),
        "team_b_score": _coerce_int(match_result.get("team_b_score"), 0),
        "duration_seconds": _coerce_int(
            match_result.get("duration_seconds"),
            0,
        ),
        "played_at": played_at,
        "ai_participants": ai_participants,
    }

    state["matches"].append(record)
    _sort_matches(state["matches"])
    _save_state(state)
    return next_match_id


def get_match_history_records() -> list[dict]:
    state = _load_state()
    records = deepcopy(state["matches"])
    _sort_matches(records)
    return records


def get_serializable_match_history_records() -> list[dict]:
    return get_match_history_records()


def _load_state() -> dict:
    path = get_demo_store_path()

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            raw_state = json.load(file_handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        state = _default_state()
        _save_state(state)
        return state

    state = _normalize_state(raw_state)
    if state != raw_state:
        _save_state(state)
    return state


def _save_state(state: dict):
    path = get_demo_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(state, file_handle, ensure_ascii=False, indent=2)


def _default_state() -> dict:
    players = []
    for index, username in enumerate(_load_seed_players(), start=1):
        players.append({"id": index, "username": username})

    return {
        "version": 1,
        "players": players,
        "matches": [],
    }


def _normalize_state(raw_state) -> dict:
    default_state = _default_state()
    if not isinstance(raw_state, dict):
        return default_state

    players = []
    raw_players = raw_state.get("players")
    if isinstance(raw_players, list):
        seen_usernames = set()
        next_id = 1
        for raw_player in raw_players:
            if isinstance(raw_player, dict):
                username = str(raw_player.get("username") or "").strip()
                player_id = _coerce_int(raw_player.get("id"), 0)
            else:
                username = str(raw_player or "").strip()
                player_id = 0

            if not username:
                continue

            username_key = username.casefold()
            if username_key in seen_usernames:
                continue

            seen_usernames.add(username_key)
            if player_id <= 0:
                player_id = next_id

            players.append({"id": player_id, "username": username})
            next_id = max(next_id, player_id + 1)

    if not players:
        players = default_state["players"]

    matches = []
    raw_matches = raw_state.get("matches")
    if isinstance(raw_matches, list):
        for fallback_match_id, raw_match in enumerate(raw_matches, start=1):
            normalized_match = _normalize_history_row(
                raw_match,
                fallback_match_id=fallback_match_id,
            )
            if normalized_match is not None:
                matches.append(normalized_match)

    _sort_matches(matches)
    return {
        "version": 1,
        "players": players,
        "matches": matches,
    }


def _load_seed_players() -> list[str]:
    raw_players = load_runtime_config().get("demo_seed_players")
    if isinstance(raw_players, list):
        candidates = raw_players
    else:
        candidates = list(DEFAULT_DEMO_PLAYERS)

    deduped_players = []
    seen_usernames = set()
    for raw_player in candidates:
        username = str(raw_player or "").strip()
        if not username:
            continue

        username_key = username.casefold()
        if username_key in seen_usernames:
            continue

        seen_usernames.add(username_key)
        deduped_players.append(username)

    if deduped_players:
        return deduped_players
    return list(DEFAULT_DEMO_PLAYERS)


def _find_player(state: dict, username: str):
    username_key = str(username or "").strip().casefold()
    for player in state["players"]:
        if str(player["username"]).casefold() == username_key:
            return player
    return None


def _append_player(state: dict, username: str) -> int:
    next_player_id = max(
        (_coerce_int(player.get("id"), 0) for player in state["players"]),
        default=0,
    ) + 1
    state["players"].append({"id": next_player_id, "username": username})
    state["players"].sort(key=lambda item: str(item["username"]).casefold())
    return next_player_id


def _ensure_player_exists_in_state(
    state: dict,
    username: str,
    *,
    allow_ai_names: bool,
) -> int | None:
    clean_username = str(username or "").strip()
    if not clean_username:
        return None
    if is_ai_name(clean_username) and not allow_ai_names:
        return None

    existing_player = _find_player(state, clean_username)
    if existing_player is not None:
        return int(existing_player["id"])

    return _append_player(state, clean_username)


def _normalize_participants(match_result: dict) -> list[dict]:
    participants = []
    raw_players = (
        match_result.get("players")
        or match_result.get("players_data")
        or []
    )

    for index, raw_player in enumerate(raw_players, start=1):
        if not isinstance(raw_player, dict):
            continue

        username = str(raw_player.get("name") or "").strip()
        if not username:
            continue

        individual_score = _coerce_int(
            raw_player.get("individual_score"),
            _coerce_int(raw_player.get("score"), 0),
        )
        control_mode = str(
            raw_player.get(
                "control_mode",
                "ai" if raw_player.get("is_ai") else "human",
            )
        ).strip().lower() or "human"

        participants.append(
            {
                "name": username,
                "team_code": _normalize_team_code(
                    raw_player.get("team") or raw_player.get("team_code")
                ),
                "individual_score": individual_score,
                "slot_number": _coerce_int(
                    raw_player.get("slot_number"),
                    _coerce_int(raw_player.get("slot"), index),
                ),
                "control_mode": control_mode,
                "is_ai": bool(raw_player.get("is_ai")) or is_ai_name(username),
            }
        )

    participants.sort(key=lambda item: item["slot_number"])
    return participants


def _normalize_history_row(
    raw_match,
    *,
    fallback_match_id: int,
) -> dict | None:
    if not isinstance(raw_match, dict):
        return None

    winner_team = _normalize_winner_team(raw_match.get("winner_team"))
    played_at = _serialize_datetime(
        raw_match.get("played_at") or datetime.now()
    )

    return {
        "match_id": _coerce_int(raw_match.get("match_id"), fallback_match_id),
        "arena_code": str(
            raw_match.get("arena_code") or "forgotten_sanctum"
        ).strip() or "forgotten_sanctum",
        "arena_label": str(
            raw_match.get("arena_label") or "Forgotten Sanctum"
        ).strip() or "Forgotten Sanctum",
        "mode_code": str(
            raw_match.get("mode_code") or "LOCAL_HUMAN"
        ).upper(),
        "source_code": str(
            raw_match.get("source_code") or "LOCAL"
        ).upper(),
        "status_code": str(
            raw_match.get("status_code") or "COMPLETED"
        ).upper(),
        "team_a_players": str(
            raw_match.get("team_a_players") or "-"
        ).strip() or "-",
        "team_b_players": str(
            raw_match.get("team_b_players") or "-"
        ).strip() or "-",
        "winner_team": winner_team,
        "winner_display": _winner_display(winner_team),
        "team_a_score": _coerce_int(raw_match.get("team_a_score"), 0),
        "team_b_score": _coerce_int(raw_match.get("team_b_score"), 0),
        "duration_seconds": _coerce_int(
            raw_match.get("duration_seconds"),
            0,
        ),
        "played_at": played_at,
        "ai_participants": _coerce_int(
            raw_match.get("ai_participants"),
            0,
        ),
    }


def _sort_matches(rows: list[dict]):
    rows.sort(
        key=lambda item: (
            _coerce_datetime(item.get("played_at")) or datetime.min,
            _coerce_int(item.get("match_id"), 0),
        ),
        reverse=True,
    )


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value

    raw_value = str(value).strip()
    if not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _serialize_datetime(value) -> str:
    coerced_datetime = _coerce_datetime(value)
    if coerced_datetime is None:
        coerced_datetime = datetime.now()
    return coerced_datetime.isoformat(sep=" ", timespec="seconds")


def _normalize_team_code(team_code: str | None) -> str:
    normalized = str(team_code or "").strip().upper()
    if normalized in {"A", "B"}:
        return normalized
    return "A"


def _normalize_winner_team(winner_team: str | None):
    normalized = str(winner_team or "").strip().upper()
    if normalized in {"A", "B"}:
        return normalized
    return None


def _winner_display(winner_team: str | None):
    normalized = _normalize_winner_team(winner_team)
    if not normalized:
        return None
    return get_team_label(normalized)
