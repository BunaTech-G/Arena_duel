from __future__ import annotations

import uuid

import mariadb

from db.database import get_connection
from game.control_models import is_ai_name


def _get_database_name(cursor) -> str:
    cursor.execute("SELECT DATABASE()")
    row = cursor.fetchone()
    return str(row[0]) if row and row[0] else ""


def _table_exists(cursor, table_name: str) -> bool:
    schema_name = _get_database_name(cursor)
    if not schema_name:
        return False

    cursor.execute(
        """
        SELECT 1
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
        """,
        (schema_name, table_name),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    schema_name = _get_database_name(cursor)
    if not schema_name:
        return False

    cursor.execute(
        """
        SELECT 1
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
          AND COLUMN_NAME = ?
        """,
        (schema_name, table_name, column_name),
    )
    return cursor.fetchone() is not None


def lobby_schema_available(cursor) -> bool:
    return (
        _table_exists(cursor, "lobby_sessions")
        and _table_exists(cursor, "lobby_members")
        and _column_exists(cursor, "lobby_sessions", "status_code")
    )


def _ensure_player_exists(cursor, username: str) -> int | None:
    clean_username = str(username or "").strip()
    if not clean_username or is_ai_name(clean_username):
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


def _ensure_arena(cursor, arena_code: str | None) -> int | None:
    clean_code = str(arena_code or "").strip()
    if not clean_code:
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


def build_lobby_invite_code() -> str:
    return str(uuid.uuid4()).split("-")[0].upper()


def open_lobby_session(
    *,
    host_name: str | None,
    invite_code: str,
    match_duration_seconds: int,
    arena_code: str = "forgotten_sanctum",
    source_code: str = "LAN",
) -> int | None:
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    try:
        if not lobby_schema_available(cursor):
            return None

        host_player_id = _ensure_player_exists(cursor, host_name or "")
        arena_id = _ensure_arena(cursor, arena_code)

        cursor.execute(
            """
            INSERT INTO lobby_sessions (
                invite_code,
                host_player_id,
                host_display_name_snapshot,
                arena_id,
                match_duration_seconds,
                source_code,
                status_code,
                opened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NOW())
            """,
            (
                invite_code,
                host_player_id,
                str(host_name or "").strip() or None,
                arena_id,
                int(match_duration_seconds),
                source_code,
                "OPEN",
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except mariadb.Error:
        conn.rollback()
        return None
    finally:
        conn.close()


def sync_lobby_session(
    lobby_session_id: int,
    *,
    players: list[dict],
    match_duration_seconds: int,
    host_name: str | None = None,
    arena_code: str = "forgotten_sanctum",
    status_code: str = "OPEN",
) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = conn.cursor()
    try:
        if not lobby_schema_available(cursor):
            return False

        host_player_id = _ensure_player_exists(cursor, host_name or "")
        arena_id = _ensure_arena(cursor, arena_code)
        normalized_status = str(status_code or "OPEN").strip().upper()

        cursor.execute(
            """
            UPDATE lobby_sessions
            SET host_player_id = ?,
                host_display_name_snapshot = ?,
                arena_id = ?,
                match_duration_seconds = ?,
                status_code = ?,
                started_at = CASE
                    WHEN ? = 'IN_MATCH' AND started_at IS NULL THEN NOW()
                    ELSE started_at
                END,
                closed_at = CASE
                    WHEN ? = 'CLOSED' THEN COALESCE(closed_at, NOW())
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (
                host_player_id,
                str(host_name or "").strip() or None,
                arena_id,
                int(match_duration_seconds),
                normalized_status,
                normalized_status,
                normalized_status,
                lobby_session_id,
            ),
        )

        active_slots = set()
        for player in sorted(
            players,
            key=lambda item: int(item.get("slot", 0)),
        ):
            slot_number = int(player.get("slot", 0) or 0)
            if slot_number <= 0:
                continue

            active_slots.add(slot_number)
            display_name = str(player.get("name", "")).strip()
            player_id = _ensure_player_exists(cursor, display_name)

            cursor.execute(
                """
                SELECT id
                FROM lobby_members
                WHERE lobby_session_id = ?
                  AND slot_number = ?
                  AND left_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (lobby_session_id, slot_number),
            )
            row = cursor.fetchone()

            if row:
                cursor.execute(
                    """
                    UPDATE lobby_members
                    SET player_id = ?,
                        display_name_snapshot = ?,
                        client_id_snapshot = ?,
                        team_code = ?,
                        ready_flag = ?
                    WHERE id = ?
                    """,
                    (
                        player_id,
                        display_name or "Invite",
                        player.get("client_id"),
                        player.get("team"),
                        1 if player.get("ready") else 0,
                        row[0],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO lobby_members (
                        lobby_session_id,
                        player_id,
                        display_name_snapshot,
                        client_id_snapshot,
                        slot_number,
                        team_code,
                        ready_flag,
                        joined_at,
                        left_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NULL)
                    """,
                    (
                        lobby_session_id,
                        player_id,
                        display_name or "Invite",
                        player.get("client_id"),
                        slot_number,
                        player.get("team"),
                        1 if player.get("ready") else 0,
                    ),
                )

        cursor.execute(
            """
            SELECT id, slot_number
            FROM lobby_members
            WHERE lobby_session_id = ?
              AND left_at IS NULL
            """,
            (lobby_session_id,),
        )
        for member_id, slot_number in cursor.fetchall():
            if int(slot_number or 0) not in active_slots:
                cursor.execute(
                    """
                    UPDATE lobby_members
                    SET ready_flag = 0,
                        left_at = COALESCE(left_at, NOW())
                    WHERE id = ?
                    """,
                    (member_id,),
                )

        conn.commit()
        return True
    except mariadb.Error:
        conn.rollback()
        return False
    finally:
        conn.close()


def close_lobby_session(lobby_session_id: int) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = conn.cursor()
    try:
        if not lobby_schema_available(cursor):
            return False

        cursor.execute(
            """
            UPDATE lobby_members
            SET ready_flag = 0,
                left_at = COALESCE(left_at, NOW())
            WHERE lobby_session_id = ?
              AND left_at IS NULL
            """,
            (lobby_session_id,),
        )
        cursor.execute(
            """
            UPDATE lobby_sessions
            SET status_code = 'CLOSED',
                closed_at = COALESCE(closed_at, NOW())
            WHERE id = ?
            """,
            (lobby_session_id,),
        )
        conn.commit()
        return True
    except mariadb.Error:
        conn.rollback()
        return False
    finally:
        conn.close()
