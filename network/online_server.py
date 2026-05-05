from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import json
import secrets
import struct
import time
from dataclasses import dataclass, field

from game.settings import MATCH_DURATION_SECONDS
from network.messages import ASSIGN_SLOT, START
from network.server import GameState, TICK_RATE


HOST = "0.0.0.0"
PORT = 27015
PROTO_VERSION = 1
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_PSEUDO_LENGTH = 24
MAX_ROOM_NAME_LENGTH = 32
MIN_ROOM_PLAYERS = 2
MAX_ROOM_PLAYERS = 6
DEFAULT_SPRITE_BY_TEAM = {
    "A": "skeleton_fighter_ember",
    "B": "skeleton_fighter_aether",
}
SERVER_CONFIG = {
    "match_duration_seconds": MATCH_DURATION_SECONDS,
}
SERVER_CAPABILITIES = {
    "ready_state": True,
}


def _default_input_state() -> dict[str, bool]:
    return {
        "up": False,
        "down": False,
        "left": False,
        "right": False,
    }


def normalize_match_duration(value: object) -> int:
    try:
        duration_seconds = int(value)
    except (TypeError, ValueError):
        return MATCH_DURATION_SECONDS

    return max(1, duration_seconds)


def apply_match_duration_override(
    game_state: GameState,
    match_duration_seconds: int,
) -> None:
    normalized_duration = normalize_match_duration(match_duration_seconds)
    game_state.match_duration_seconds = normalized_duration
    game_state.ends_at = game_state.started_at + normalized_duration


@dataclass(slots=True)
class ClientSession:
    client_id: str
    writer: asyncio.StreamWriter
    pseudo: str = "anonymous"
    room_id: str | None = None
    ready_to_start: bool = False
    slot: int | None = None
    team: str | None = None
    sprite_id: str = ""
    input_state: dict[str, bool] = field(default_factory=_default_input_state)
    connected_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class RoomState:
    room_id: str
    name: str
    max_players: int
    match_duration_seconds: int = MATCH_DURATION_SECONDS
    state: str = "lobby"
    client_ids: list[str] = field(default_factory=list)
    host_client_id: str | None = None
    game_state: GameState | None = None
    game_task: asyncio.Task | None = None
    created_at: float = field(default_factory=time.time)


clients: dict[str, ClientSession] = {}
rooms: dict[str, RoomState] = {}
registry_lock = asyncio.Lock()


def pack_msg(obj: dict) -> bytes:
    raw = json.dumps(
        obj,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return struct.pack("!I", len(raw)) + raw


async def read_exactly(reader: asyncio.StreamReader, size: int) -> bytes:
    return await reader.readexactly(size)


async def read_msg(reader: asyncio.StreamReader) -> dict:
    header = await read_exactly(reader, 4)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > MAX_MESSAGE_BYTES:
        raise ValueError("ONLINE_MESSAGE_TOO_LARGE")

    raw = await read_exactly(reader, size)
    return json.loads(raw.decode("utf-8"))


async def send(writer: asyncio.StreamWriter, obj: dict) -> None:
    writer.write(pack_msg(obj))
    await writer.drain()


def normalize_pseudo(value: object) -> str:
    pseudo = str(value or "anonymous").strip()
    if not pseudo:
        pseudo = "anonymous"
    return pseudo[:MAX_PSEUDO_LENGTH]


def normalize_room_name(value: object) -> str:
    room_name = str(value or "Room").strip()
    if not room_name:
        room_name = "Room"
    return room_name[:MAX_ROOM_NAME_LENGTH]


def normalize_max_players(value: object) -> int:
    try:
        max_players = int(value)
    except (TypeError, ValueError):
        max_players = MIN_ROOM_PLAYERS

    return max(MIN_ROOM_PLAYERS, min(MAX_ROOM_PLAYERS, max_players))


def generate_client_id() -> str:
    return f"c{secrets.token_hex(4)}"


def generate_room_id() -> str:
    stamp = int(time.time() * 1000)
    token = secrets.token_hex(2)
    return f"r{stamp}{token}"


def _supports_start_server_keep_alive() -> bool:
    try:
        start_server_signature = inspect.signature(asyncio.start_server)
        return "keep_alive" in start_server_signature.parameters
    except (TypeError, ValueError):
        return False


def build_start_server_kwargs() -> dict[str, bool]:
    if _supports_start_server_keep_alive():
        return {"keep_alive": True}
    return {}


def build_welcome_payload() -> dict:
    return {
        "type": "WELCOME",
        "proto": PROTO_VERSION,
        "capabilities": dict(SERVER_CAPABILITIES),
    }


def default_sprite_id_for_team(team_code: str) -> str:
    return DEFAULT_SPRITE_BY_TEAM.get(
        str(team_code or "A").strip().upper(),
        DEFAULT_SPRITE_BY_TEAM["A"],
    )


def prune_room_clients_unlocked(room: RoomState) -> None:
    room.client_ids = [
        client_id for client_id in room.client_ids if client_id in clients
    ]


def rebalance_room_assignments_unlocked(room: RoomState) -> None:
    prune_room_clients_unlocked(room)
    team_counts = {"A": 0, "B": 0}

    for slot_index, client_id in enumerate(room.client_ids, start=1):
        client = clients.get(client_id)
        if client is None:
            continue

        team = "A" if team_counts["A"] <= team_counts["B"] else "B"
        client.slot = slot_index
        client.team = team
        client.sprite_id = default_sprite_id_for_team(team)
        team_counts[team] += 1


def reset_room_inputs_unlocked(room: RoomState) -> None:
    for client_id in room.client_ids:
        client = clients.get(client_id)
        if client is None:
            continue
        client.input_state = _default_input_state()


def reset_room_ready_states_unlocked(room: RoomState) -> None:
    for client_id in room.client_ids:
        client = clients.get(client_id)
        if client is None:
            continue
        client.ready_to_start = False


def serialize_assignment_unlocked(client: ClientSession) -> dict:
    return {
        "type": ASSIGN_SLOT,
        "client_id": client.client_id,
        "slot": client.slot,
        "team": client.team,
        "sprite_id": client.sprite_id,
    }


def build_match_snapshot_unlocked(room: RoomState) -> dict:
    snapshot = {}
    for client_id in room.client_ids:
        client = clients.get(client_id)
        if client is None or client.slot is None or client.team is None:
            continue

        snapshot[client_id] = {
            "client_id": client.client_id,
            "name": client.pseudo,
            "slot": client.slot,
            "team": client.team,
            "sprite_id": client.sprite_id,
            "ready": True,
            "input": dict(client.input_state),
            "handler": None,
        }
    return snapshot


def room_players_unlocked(room: RoomState) -> list[str]:
    prune_room_clients_unlocked(room)
    return [
        clients[client_id].pseudo
        for client_id in room.client_ids
        if client_id in clients
    ]


def room_ready_players_unlocked(room: RoomState) -> list[str]:
    prune_room_clients_unlocked(room)
    return [
        clients[client_id].pseudo
        for client_id in room.client_ids
        if client_id in clients and clients[client_id].ready_to_start
    ]


def room_all_players_ready_unlocked(room: RoomState) -> bool:
    prune_room_clients_unlocked(room)
    if not room.client_ids:
        return False

    for client_id in room.client_ids:
        client = clients.get(client_id)
        if client is None or not client.ready_to_start:
            return False

    return True


def room_host_unlocked(room: RoomState) -> tuple[str | None, str | None]:
    prune_room_clients_unlocked(room)
    host_client_id = room.host_client_id
    if host_client_id in clients:
        return host_client_id, clients[host_client_id].pseudo

    for client_id in room.client_ids:
        if client_id in clients:
            room.host_client_id = client_id
            return client_id, clients[client_id].pseudo

    room.host_client_id = None
    return None, None


def serialize_room_summary_unlocked(room: RoomState) -> dict:
    host_client_id, host_pseudo = room_host_unlocked(room)
    return {
        "room_id": room.room_id,
        "name": room.name,
        "players": len(room_players_unlocked(room)),
        "max_players": room.max_players,
        "match_duration_seconds": room.match_duration_seconds,
        "state": room.state,
        "host_client_id": host_client_id,
        "host_pseudo": host_pseudo,
    }


def serialize_room_state_unlocked(room: RoomState) -> dict:
    host_client_id, host_pseudo = room_host_unlocked(room)
    return {
        "room_id": room.room_id,
        "name": room.name,
        "players": room_players_unlocked(room),
        "ready_players": room_ready_players_unlocked(room),
        "max_players": room.max_players,
        "match_duration_seconds": room.match_duration_seconds,
        "state": room.state,
        "host_client_id": host_client_id,
        "host_pseudo": host_pseudo,
    }


async def read_login_or_prelogin_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> dict:
    while True:
        message = await read_msg(reader)
        message_type = str(message.get("type") or "").strip().upper()

        if message_type == "PING":
            await send(writer, {"type": "PONG", "ts": time.time()})
            continue

        if message_type == "LIST_ROOMS":
            await send(
                writer,
                {
                    "type": "ROOMS",
                    "rooms": await list_rooms(),
                },
            )
            continue

        return message


async def list_rooms() -> list[dict]:
    async with registry_lock:
        ordered_rooms = sorted(
            rooms.values(),
            key=lambda room: (
                room.state != "lobby",
                room.created_at,
                room.room_id,
            ),
        )
        return [serialize_room_summary_unlocked(room) for room in ordered_rooms]


async def send_error(client_id: str, code: str, **extra_fields) -> None:
    async with registry_lock:
        client = clients.get(client_id)
        writer = None if client is None else client.writer

    if writer is None:
        return

    payload = {"type": "ERROR", "code": code}
    payload.update(extra_fields)
    await send(writer, payload)


async def broadcast_room(room_id: str, obj: dict) -> None:
    async with registry_lock:
        room = rooms.get(room_id)
        if room is None:
            return
        targets = [
            clients[client_id].writer
            for client_id in room.client_ids
            if client_id in clients
        ]

    for writer in targets:
        try:
            await send(writer, obj)
        except (ConnectionError, OSError, RuntimeError):
            pass


async def broadcast_room_update(room_id: str) -> None:
    async with registry_lock:
        room = rooms.get(room_id)
        if room is None:
            return
        payload = serialize_room_state_unlocked(room)

    await broadcast_room(room_id, {"type": "ROOM_UPDATE", "room": payload})


async def broadcast_room_assignments(room_id: str) -> None:
    async with registry_lock:
        room = rooms.get(room_id)
        if room is None:
            return

        if room.state != "lobby":
            return

        rebalance_room_assignments_unlocked(room)
        targets = []
        for client_id in room.client_ids:
            client = clients.get(client_id)
            if client is None:
                continue
            targets.append(
                (
                    client.writer,
                    serialize_assignment_unlocked(client),
                )
            )

    for writer, payload in targets:
        try:
            await send(writer, payload)
        except (ConnectionError, OSError, RuntimeError):
            pass


async def broadcast_host_changed(room_id: str) -> None:
    async with registry_lock:
        room = rooms.get(room_id)
        if room is None:
            return
        host_client_id, host_pseudo = room_host_unlocked(room)
        if host_client_id is None or host_pseudo is None:
            return

    await broadcast_room(
        room_id,
        {
            "type": "HOST_CHANGED",
            "room_id": room_id,
            "host_client_id": host_client_id,
            "host_pseudo": host_pseudo,
        },
    )


async def leave_room(client_id: str) -> None:
    room_id = None
    host_changed = False
    room_state = None
    game_task = None

    async with registry_lock:
        client = clients.get(client_id)
        if client is None or client.room_id is None:
            return

        room_id = client.room_id
        client.room_id = None
        room = rooms.get(room_id)
        if room is None:
            return

        room_state = room.state
        previous_host = room.host_client_id
        room.client_ids = [
            existing_client_id
            for existing_client_id in room.client_ids
            if (existing_client_id != client_id and existing_client_id in clients)
        ]
        client.ready_to_start = False
        client.slot = None
        client.team = None
        client.input_state = _default_input_state()

        if not room.client_ids:
            game_task = room.game_task
            rooms.pop(room_id, None)
            return

        if previous_host == client_id or previous_host not in room.client_ids:
            room.host_client_id = room.client_ids[0]
            host_changed = room.host_client_id != previous_host

        if room.state == "lobby":
            rebalance_room_assignments_unlocked(room)

    if room_id is None:
        return

    if game_task is not None:
        game_task.cancel()

    if host_changed:
        await broadcast_host_changed(room_id)
    await broadcast_room_update(room_id)
    if room_state == "lobby":
        await broadcast_room_assignments(room_id)


async def join_room(client_id: str, room_id: object) -> None:
    normalized_room_id = str(room_id or "").strip()
    if not normalized_room_id:
        await send_error(client_id, "ROOM_NOT_FOUND")
        return

    async with registry_lock:
        client = clients.get(client_id)
        if client is None:
            return
        current_room_id = client.room_id
        target_room = rooms.get(normalized_room_id)
        writer = client.writer

        if target_room is None:
            target_room_full = False
            target_room_started = False
        else:
            target_room_started = target_room.state != "lobby"
            target_room_full = (
                client_id not in target_room.client_ids
                and len(target_room.client_ids) >= target_room.max_players
            )

    if target_room is None:
        await send(writer, {"type": "ERROR", "code": "ROOM_NOT_FOUND"})
        return

    if target_room_full:
        await send(writer, {"type": "ERROR", "code": "ROOM_FULL"})
        return

    if target_room_started:
        await send(
            writer,
            {"type": "ERROR", "code": "MATCH_ALREADY_STARTED"},
        )
        return

    if current_room_id is not None and current_room_id != normalized_room_id:
        await leave_room(client_id)

    async with registry_lock:
        client = clients.get(client_id)
        target_room = rooms.get(normalized_room_id)
        if client is None:
            return
        writer = client.writer
        assignment_payload = None

        if target_room is None:
            room_payload = None
        elif target_room.state != "lobby":
            room_payload = "MATCH_ALREADY_STARTED"
        else:
            if (
                client_id not in target_room.client_ids
                and len(target_room.client_ids) >= target_room.max_players
            ):
                room_payload = "ROOM_FULL"
            else:
                if client_id not in target_room.client_ids:
                    target_room.client_ids.append(client_id)
                client.room_id = normalized_room_id
                client.ready_to_start = False
                if target_room.host_client_id is None:
                    target_room.host_client_id = target_room.client_ids[0]
                rebalance_room_assignments_unlocked(target_room)
                room_payload = serialize_room_state_unlocked(target_room)
                assignment_payload = serialize_assignment_unlocked(client)

    if target_room is None:
        await send(writer, {"type": "ERROR", "code": "ROOM_NOT_FOUND"})
        return

    if room_payload == "ROOM_FULL":
        await send(writer, {"type": "ERROR", "code": "ROOM_FULL"})
        return

    if room_payload == "MATCH_ALREADY_STARTED":
        await send(
            writer,
            {"type": "ERROR", "code": "MATCH_ALREADY_STARTED"},
        )
        return

    await send(
        writer,
        {
            "type": "JOINED",
            "room_id": normalized_room_id,
            "host_client_id": room_payload["host_client_id"],
            "host_pseudo": room_payload["host_pseudo"],
        },
    )
    await send(writer, assignment_payload)
    await broadcast_room_update(normalized_room_id)
    await broadcast_room_assignments(normalized_room_id)


async def run_room_match(room_id: str) -> None:
    dt = 1.0 / TICK_RATE
    next_tick = time.monotonic()

    try:
        while True:
            async with registry_lock:
                room = rooms.get(room_id)
                if room is None or room.state != "in_game" or room.game_state is None:
                    return

                game_state = room.game_state
                snapshot = build_match_snapshot_unlocked(room)

            game_state.update(dt, snapshot)
            await broadcast_room(room_id, game_state.export_state())

            if game_state.is_finished():
                end_message = game_state.build_end_message()

                async with registry_lock:
                    room = rooms.get(room_id)
                    if room is not None:
                        room.state = "lobby"
                        room.game_state = None
                        room.game_task = None
                        reset_room_inputs_unlocked(room)
                        reset_room_ready_states_unlocked(room)
                        rebalance_room_assignments_unlocked(room)

                await broadcast_room(room_id, end_message)
                await broadcast_room_update(room_id)
                await broadcast_room_assignments(room_id)
                return

            next_tick += dt
            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                next_tick = time.monotonic()
    finally:
        async with registry_lock:
            room = rooms.get(room_id)
            if room is not None and room.game_task is asyncio.current_task():
                room.game_task = None


async def create_room(
    client_id: str,
    name: object,
    max_players: object,
    match_duration_seconds: object | None = None,
) -> None:
    normalized_name = normalize_room_name(name)
    normalized_max_players = normalize_max_players(max_players)
    normalized_match_duration = normalize_match_duration(
        SERVER_CONFIG["match_duration_seconds"]
        if match_duration_seconds is None
        else match_duration_seconds
    )

    await leave_room(client_id)

    async with registry_lock:
        room_id = generate_room_id()
        while room_id in rooms:
            room_id = generate_room_id()

        rooms[room_id] = RoomState(
            room_id=room_id,
            name=normalized_name,
            max_players=normalized_max_players,
            match_duration_seconds=normalized_match_duration,
        )

        client = clients.get(client_id)
        if client is None:
            rooms.pop(room_id, None)
            return
        writer = client.writer

    await send(
        writer,
        {
            "type": "ROOM_CREATED",
            "room_id": room_id,
            "name": normalized_name,
            "max_players": normalized_max_players,
            "match_duration_seconds": normalized_match_duration,
        },
    )
    await join_room(client_id, room_id)


async def set_ready_state(client_id: str, ready: object) -> None:
    room_id = None

    async with registry_lock:
        client = clients.get(client_id)
        if client is None or client.room_id is None:
            writer = None if client is None else client.writer
            error_code = "NOT_IN_ROOM"
        else:
            writer = client.writer
            room = rooms.get(client.room_id)
            if room is None:
                error_code = "ROOM_NOT_FOUND"
            elif room.state != "lobby":
                error_code = "MATCH_ALREADY_STARTED"
            else:
                client.ready_to_start = bool(ready)
                room_id = room.room_id
                error_code = None

    if error_code is not None:
        if writer is not None:
            await send(writer, {"type": "ERROR", "code": error_code})
        return

    if room_id is not None:
        await broadcast_room_update(room_id)


async def start_match(client_id: str) -> None:
    room_id = None

    async with registry_lock:
        client = clients.get(client_id)
        if client is None or client.room_id is None:
            writer = None if client is None else client.writer
            room_payload = None
            error_code = "NOT_IN_ROOM"
        else:
            writer = client.writer
            room = rooms.get(client.room_id)
            if room is None:
                room_payload = None
                error_code = "ROOM_NOT_FOUND"
            elif room.state != "lobby":
                room_payload = None
                error_code = "MATCH_ALREADY_STARTED"
            elif room.host_client_id != client_id:
                room_payload = None
                error_code = "HOST_ONLY"
            elif len(room.client_ids) < MIN_ROOM_PLAYERS:
                room_payload = None
                error_code = "NEED_MORE_PLAYERS"
            elif len(room.client_ids) < room.max_players:
                room_payload = None
                error_code = "ROOM_NOT_FULL"
            elif not room_all_players_ready_unlocked(room):
                room_payload = None
                error_code = "PLAYERS_NOT_READY"
            else:
                rebalance_room_assignments_unlocked(room)
                snapshot = build_match_snapshot_unlocked(room)
                room.game_state = GameState(snapshot)
                apply_match_duration_override(
                    room.game_state,
                    room.match_duration_seconds,
                )
                room.state = "in_game"
                room_payload = serialize_room_state_unlocked(room)
                room_id = room.room_id
                error_code = None

    if error_code is not None:
        if writer is not None:
            await send(writer, {"type": "ERROR", "code": error_code})
        return

    match_task = asyncio.create_task(run_room_match(room_id))
    async with registry_lock:
        room = rooms.get(room_id)
        if room is not None:
            room.game_task = match_task

    await broadcast_room(
        room_id,
        {
            "type": "MATCH_STARTED",
            "room_id": room_id,
            "host_client_id": room_payload["host_client_id"],
            "host_pseudo": room_payload["host_pseudo"],
        },
    )
    await broadcast_room(room_id, {"type": START, "room_id": room_id})
    await broadcast_room_update(room_id)


async def handle(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    peer = writer.get_extra_info("peername")
    client_id = generate_client_id()

    async with registry_lock:
        clients[client_id] = ClientSession(client_id=client_id, writer=writer)

    try:
        hello = await read_msg(reader)
        if str(hello.get("type") or "").strip().upper() != "HELLO":
            await send(writer, {"type": "ERROR", "code": "BAD_HANDSHAKE"})
            return

        if int(hello.get("proto") or 0) != PROTO_VERSION:
            await send(
                writer,
                {
                    "type": "ERROR",
                    "code": "PROTO_MISMATCH",
                    "server_proto": PROTO_VERSION,
                },
            )
            return

        await send(writer, build_welcome_payload())

        login = await read_login_or_prelogin_request(reader, writer)
        if str(login.get("type") or "").strip().upper() != "LOGIN":
            await send(writer, {"type": "ERROR", "code": "LOGIN_REQUIRED"})
            return

        pseudo = normalize_pseudo(login.get("pseudo"))
        async with registry_lock:
            client = clients.get(client_id)
            if client is not None:
                client.pseudo = pseudo

        await send(writer, {"type": "LOGIN_OK", "pseudo": pseudo})
        print(f"[ONLINE] {peer} connecte en tant que {pseudo}")

        while True:
            message = await read_msg(reader)
            message_type = str(message.get("type") or "").strip().upper()

            if message_type == "PING":
                await send(writer, {"type": "PONG", "ts": time.time()})
                continue

            if message_type == "LIST_ROOMS":
                await send(
                    writer,
                    {
                        "type": "ROOMS",
                        "rooms": await list_rooms(),
                    },
                )
                continue

            if message_type == "CREATE_ROOM":
                await create_room(
                    client_id,
                    message.get("name"),
                    message.get("max_players"),
                    message.get("match_duration_seconds"),
                )
                continue

            if message_type == "JOIN_ROOM":
                await join_room(client_id, message.get("room_id"))
                continue

            if message_type == "LEAVE_ROOM":
                await leave_room(client_id)
                continue

            if message_type == "START_MATCH":
                await start_match(client_id)
                continue

            if message_type == "SET_READY":
                await set_ready_state(client_id, message.get("ready", False))
                continue

            if message_type == "INPUT":
                async with registry_lock:
                    client = clients.get(client_id)
                    if client is not None:
                        client.input_state = {
                            "up": bool(message.get("up", False)),
                            "down": bool(message.get("down", False)),
                            "left": bool(message.get("left", False)),
                            "right": bool(message.get("right", False)),
                        }
                continue

            await send(
                writer,
                {
                    "type": "ERROR",
                    "code": "UNKNOWN_TYPE",
                    "got": message_type,
                },
            )
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        struct.error,
    ) as error:
        print(f"[ONLINE] Erreur client {peer}: {type(error).__name__}: {error}")
    finally:
        await leave_room(client_id)
        async with registry_lock:
            clients.pop(client_id, None)
        with contextlib.suppress(Exception):
            writer.close()
            await writer.wait_closed()
        print(f"[ONLINE] {peer} deconnecte")


async def main(
    host: str,
    port: int,
    match_duration_seconds: int,
) -> None:
    SERVER_CONFIG["match_duration_seconds"] = normalize_match_duration(
        match_duration_seconds
    )

    server = await asyncio.start_server(
        handle,
        host,
        port,
        **build_start_server_kwargs(),
    )
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(
        f"[ONLINE] Serveur TCP+JSON en ecoute sur {addresses} "
        f"(match {SERVER_CONFIG['match_duration_seconds']}s)"
    )
    async with server:
        await server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serveur online asyncio Arena Duel.",
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--match-duration",
        type=int,
        default=MATCH_DURATION_SECONDS,
        help=(
            "Durée des matchs online en secondes. Pratique pour les smoke tests locaux."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(
        main(
            arguments.host,
            arguments.port,
            arguments.match_duration,
        )
    )
