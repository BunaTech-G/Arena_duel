from __future__ import annotations

from datetime import datetime

import mariadb

from db import demo_store
from db.database import get_connection
from db.schema_utils import column_exists, relation_exists
from game.control_models import AI_CONTROL_MODE, HUMAN_CONTROL_MODE, is_ai_name
from game.match_text import get_team_label


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


def _supports_v2_schema(cursor) -> bool:
    return column_exists(cursor, "matches", "mode_code") and column_exists(
        cursor, "match_players", "display_name_snapshot"
    )


def _history_view_available(cursor) -> bool:
    return relation_exists(cursor, "v_match_history_cards", "VIEW")


def _ensure_player_exists(
    cursor,
    username: str,
    *,
    allow_ai_names: bool,
) -> int | None:
    clean_username = str(username or "").strip()
    if not clean_username:
        return None
    if is_ai_name(clean_username) and not allow_ai_names:
        return None

    cursor.execute(
        "SELECT id FROM players WHERE username = ?",
        (clean_username,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO players (username) VALUES (?)",
        (clean_username,),
    )
    return cursor.lastrowid


def ensure_player_exists_by_name(
    username: str,
    *,
    allow_ai_names: bool = False,
):
    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.ensure_player_exists_by_name(
                username,
                allow_ai_names=allow_ai_names,
            )
        return None

    cursor = conn.cursor()
    try:
        player_id = _ensure_player_exists(
            cursor,
            username,
            allow_ai_names=allow_ai_names,
        )
        conn.commit()
        return player_id
    except mariadb.Error:
        conn.rollback()
        return None
    finally:
        conn.close()


def _ensure_arena(cursor, arena_code: str | None):
    clean_code = str(arena_code or "").strip()
    if not clean_code or not relation_exists(cursor, "arenas", "BASE TABLE"):
        return None

    cursor.execute(
        "SELECT id FROM arenas WHERE code = ?",
        (clean_code,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO arenas (
            code,
            label,
            asset_path,
            layout_version,
            active
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            clean_code,
            clean_code.replace("_", " ").title(),
            f"assets/maps/{clean_code}/layout.json",
            "1",
            1,
        ),
    )
    return cursor.lastrowid


def _normalize_participants(match_result: dict) -> list[dict]:
    participants = []
    raw_players = match_result.get("players") or match_result.get("players_data") or []

    for index, raw_player in enumerate(raw_players, start=1):
        name = str(raw_player.get("name", "")).strip()
        if not name:
            continue

        control_mode = (
            str(
                raw_player.get(
                    "control_mode",
                    (
                        AI_CONTROL_MODE
                        if raw_player.get("is_ai")
                        else HUMAN_CONTROL_MODE
                    ),
                )
                or HUMAN_CONTROL_MODE
            )
            .strip()
            .lower()
        )
        is_ai = (
            bool(raw_player.get("is_ai"))
            or control_mode == AI_CONTROL_MODE
            or is_ai_name(name)
        )
        slot_number = raw_player.get(
            "slot_number",
            raw_player.get("slot", raw_player.get("ui_slot", index)),
        )

        participants.append(
            {
                "name": name,
                "team_code": _normalize_team_code(
                    raw_player.get("team", raw_player.get("team_code"))
                ),
                "individual_score": _coerce_int(
                    raw_player.get(
                        "individual_score",
                        raw_player.get("score", 0),
                    )
                ),
                "slot_number": _coerce_int(slot_number, index),
                "control_mode": control_mode,
                "is_ai": is_ai,
                "ai_difficulty_code": raw_player.get(
                    "ai_difficulty_code",
                    raw_player.get("ai_difficulty"),
                ),
                "ai_profile_code": raw_player.get(
                    "ai_profile_code",
                    raw_player.get("ai_profile"),
                ),
                "ready_at_start": raw_player.get("ready_at_start"),
            }
        )

    return participants


def _infer_mode_code(source_code: str, participants: list[dict]) -> str:
    if source_code == "LAN":
        return "LAN"
    if any(player["is_ai"] for player in participants):
        return "LOCAL_AI"
    return "LOCAL_HUMAN"


def _normalize_match_result(match_result: dict) -> dict:
    participants = _normalize_participants(match_result)
    source_code = str(match_result.get("source_code") or "LOCAL").strip().upper()
    if source_code not in {"LOCAL", "LAN", "LEGACY"}:
        source_code = "LOCAL"

    mode_code = str(match_result.get("mode_code") or "").strip().upper()
    if not mode_code:
        mode_code = _infer_mode_code(source_code, participants)

    finished_at = _coerce_datetime(match_result.get("finished_at")) or datetime.now()
    played_at = _coerce_datetime(match_result.get("played_at")) or finished_at

    return {
        "team_a_score": _coerce_int(match_result.get("team_a_score", 0)),
        "team_b_score": _coerce_int(match_result.get("team_b_score", 0)),
        "winner_team": _normalize_winner_team(match_result.get("winner_team")),
        "duration_seconds": _coerce_int(
            match_result.get("duration_seconds", 60),
            60,
        ),
        "mode_code": mode_code,
        "source_code": source_code,
        "status_code": str(match_result.get("status_code") or "COMPLETED")
        .strip()
        .upper(),
        "arena_code": str(
            match_result.get("arena_code") or match_result.get("map_id") or ""
        ).strip(),
        "lobby_session_id": match_result.get("lobby_session_id"),
        "created_by_player_id": match_result.get("created_by_player_id"),
        "started_at": _coerce_datetime(match_result.get("started_at")),
        "finished_at": finished_at,
        "played_at": played_at,
        "participants": participants,
    }


def _insert_match_v2(cursor, payload: dict) -> int:
    arena_id = _ensure_arena(cursor, payload["arena_code"])

    cursor.execute(
        """
        INSERT INTO matches (
            mode_code,
            source_code,
            status_code,
            arena_id,
            arena_code_snapshot,
            lobby_session_id,
            created_by_player_id,
            team_a_score,
            team_b_score,
            winner_team,
            duration_seconds,
            started_at,
            finished_at,
            played_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["mode_code"],
            payload["source_code"],
            payload["status_code"],
            arena_id,
            payload["arena_code"] or None,
            payload["lobby_session_id"],
            payload["created_by_player_id"],
            payload["team_a_score"],
            payload["team_b_score"],
            payload["winner_team"],
            payload["duration_seconds"],
            payload["started_at"],
            payload["finished_at"],
            payload["played_at"],
        ),
    )
    match_id = cursor.lastrowid

    for player in payload["participants"]:
        player_id = None
        if not player["is_ai"]:
            player_id = _ensure_player_exists(
                cursor,
                player["name"],
                allow_ai_names=False,
            )

        cursor.execute(
            """
            INSERT INTO match_players (
                match_id,
                player_id,
                display_name_snapshot,
                team_code,
                slot_number,
                control_mode,
                is_ai,
                ai_difficulty_code,
                ai_profile_code,
                ready_at_start,
                individual_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                player_id,
                player["name"],
                player["team_code"],
                player["slot_number"],
                player["control_mode"],
                1 if player["is_ai"] else 0,
                player["ai_difficulty_code"],
                player["ai_profile_code"],
                player["ready_at_start"],
                player["individual_score"],
            ),
        )

    return match_id


def _insert_match_legacy(cursor, payload: dict) -> int:
    cursor.execute(
        """
        INSERT INTO matches (
            team_a_score,
            team_b_score,
            winner_team,
            duration_seconds
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            payload["team_a_score"],
            payload["team_b_score"],
            payload["winner_team"],
            payload["duration_seconds"],
        ),
    )
    match_id = cursor.lastrowid

    for player in payload["participants"]:
        player_id = _ensure_player_exists(
            cursor,
            player["name"],
            allow_ai_names=True,
        )
        if not player_id:
            continue

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
            (
                match_id,
                player_id,
                player["team_code"],
                player["individual_score"],
            ),
        )

    return match_id


def save_match_result(match_result: dict) -> int:
    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.save_match_result(match_result)
        raise RuntimeError("Le sanctuaire des chroniques est indisponible.")

    cursor = conn.cursor()
    try:
        payload = _normalize_match_result(match_result)
        if _supports_v2_schema(cursor):
            match_id = _insert_match_v2(cursor, payload)
        else:
            match_id = _insert_match_legacy(cursor, payload)

        conn.commit()
        return match_id
    except RuntimeError:
        conn.rollback()
        raise
    except mariadb.Error as error:
        conn.rollback()
        raise RuntimeError(f"MariaDB n'a pas pu archiver la joute : {error}") from error
    finally:
        conn.close()


def _load_history_from_v2(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT
            match_id,
            arena_code,
            arena_label,
            mode_code,
            source_code,
            status_code,
            team_a_players,
            team_b_players,
            team_a_score,
            team_b_score,
            winner_team,
            duration_seconds,
            played_at,
            ai_participants
        FROM v_match_history_cards
        ORDER BY played_at DESC, match_id DESC
        """
    )

    rows = cursor.fetchall()
    history_rows = []
    for row in rows:
        (
            match_id,
            arena_code,
            arena_label,
            mode_code,
            source_code,
            status_code,
            team_a_players,
            team_b_players,
            team_a_score,
            team_b_score,
            winner_team,
            duration_seconds,
            played_at,
            ai_participants,
        ) = row

        history_rows.append(
            {
                "match_id": match_id,
                "arena_code": arena_code,
                "arena_label": arena_label,
                "mode_code": mode_code,
                "source_code": source_code,
                "status_code": status_code,
                "team_a_players": team_a_players or "-",
                "team_b_players": team_b_players or "-",
                "winner_team": _normalize_winner_team(winner_team),
                "winner_display": _winner_display(winner_team),
                "team_a_score": _coerce_int(team_a_score),
                "team_b_score": _coerce_int(team_b_score),
                "duration_seconds": _coerce_int(duration_seconds),
                "played_at": played_at,
                "ai_participants": _coerce_int(ai_participants),
            }
        )

    return history_rows


def _load_history_from_legacy(cursor) -> list[dict]:
    cursor.execute(
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
    rows = cursor.fetchall()
    if not rows:
        return []

    matches_map = {}
    for row in rows:
        (
            match_id,
            team_a_score,
            team_b_score,
            winner_team,
            duration_seconds,
            played_at,
            username,
            team_code,
        ) = row

        if match_id not in matches_map:
            matches_map[match_id] = {
                "match_id": match_id,
                "arena_code": "forgotten_sanctum",
                "arena_label": "Forgotten Sanctum",
                "mode_code": "LEGACY",
                "source_code": "LEGACY",
                "status_code": "COMPLETED",
                "team_a_players": [],
                "team_b_players": [],
                "winner_team": _normalize_winner_team(winner_team),
                "winner_display": _winner_display(winner_team),
                "team_a_score": _coerce_int(team_a_score),
                "team_b_score": _coerce_int(team_b_score),
                "duration_seconds": _coerce_int(duration_seconds),
                "played_at": played_at,
                "ai_participants": 0,
            }

        if team_code == "A":
            matches_map[match_id]["team_a_players"].append(username)
        elif team_code == "B":
            matches_map[match_id]["team_b_players"].append(username)

        if is_ai_name(username):
            matches_map[match_id]["ai_participants"] += 1

    history_rows = []
    for record in matches_map.values():
        history_rows.append(
            {
                **record,
                "team_a_players": ", ".join(record["team_a_players"]) or "-",
                "team_b_players": ", ".join(record["team_b_players"]) or "-",
            }
        )

    history_rows.sort(
        key=lambda item: (
            (item["played_at"] if item["played_at"] is not None else datetime.min),
            item["match_id"],
        ),
        reverse=True,
    )
    return history_rows


def get_match_history_records() -> list[dict]:
    conn = get_connection()
    if not conn:
        if demo_store.is_demo_storage_enabled():
            return demo_store.get_match_history_records()
        return []

    cursor = conn.cursor()
    try:
        if _history_view_available(cursor):
            return _load_history_from_v2(cursor)
        return _load_history_from_legacy(cursor)
    except mariadb.Error:
        return []
    finally:
        conn.close()


def get_serializable_match_history_records() -> list[dict]:
    rows = get_match_history_records()
    serialized_rows = []

    for row in rows:
        serialized_row = dict(row)
        if serialized_row.get("played_at") is not None:
            serialized_row["played_at"] = str(serialized_row["played_at"])
        serialized_rows.append(serialized_row)

    return serialized_rows
