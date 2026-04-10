import argparse
import json
import math
import socketserver
import threading
import time
import uuid
from datetime import datetime

from hardware.service import create_match_hardware_service
from game.arena_layout import (
    DEFAULT_MAP_ID,
    get_team_spawn_positions,
    load_arena_layout,
    random_free_point,
    resolve_movement,
)
from game.match_text import format_winner_text, get_winner_team
from game.settings import (
    MATCH_DURATION_SECONDS,
    ORB_RADIUS,
    ORB_SPAWN_COUNT,
    PLAYER_RADIUS,
    coerce_match_duration,
)
from network.messages import (
    HELLO,
    ASSIGN_SLOT,
    LOBBY_STATE,
    READY,
    PING,
    PONG,
    ERROR,
    INPUT,
    START,
    STATE,
    END,
    REQUEST_HISTORY,
    HISTORY_DATA,
    SET_MATCH_DURATION,
)
from network.protocol import send_message_binary, receive_message_binary
from db.lobby_repository import (
    build_lobby_invite_code,
    close_lobby_session,
    open_lobby_session,
    sync_lobby_session,
)
from db.network_match_repository import save_network_match_result
from db.matches import get_serializable_match_history
from network.net_utils import (
    format_bind_error,
    format_endpoint,
    get_lan_address_info,
    get_network_logger,
)

MAX_PLAYERS = 6

PLAYER_SPEED = 260
ORB_COUNT = ORB_SPAWN_COUNT

TICK_RATE = 20
LOGGER = get_network_logger()


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


class LobbyState:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = {}  # client_id -> info
        self.host_client_id = None
        self.match_duration_seconds = MATCH_DURATION_SECONDS

    def get_used_slots(self):
        return {info["slot"] for info in self.clients.values()}

    def get_next_free_slot(self):
        used = self.get_used_slots()
        for slot in range(1, MAX_PLAYERS + 1):
            if slot not in used:
                return slot
        return None

    def get_team_counts(self):
        counts = {"A": 0, "B": 0}

        for info in self.clients.values():
            team = info.get("team")
            if team == "A":
                counts["A"] += 1
            elif team == "B":
                counts["B"] += 1

        return counts

    def get_next_balanced_team(self) -> str:
        counts = self.get_team_counts()

        if counts["A"] <= counts["B"]:
            return "A"
        else:
            return "B"

    def add_client(self, name: str, handler, is_host: bool = False):
        with self.lock:
            if len(self.clients) >= MAX_PLAYERS:
                return None

            slot = self.get_next_free_slot()
            if slot is None:
                return None

            assigned_team = self.get_next_balanced_team()
            client_id = str(uuid.uuid4())[:8]

            info = {
                "client_id": client_id,
                "name": name,
                "slot": slot,
                "team": assigned_team,
                "host": bool(is_host),
                "ready": False,
                "handler": handler,
                "input": {
                    "up": False,
                    "down": False,
                    "left": False,
                    "right": False,
                },
            }
            self.clients[client_id] = info
            if is_host:
                self.host_client_id = client_id
            return info

    def remove_client(self, client_id: str):
        with self.lock:
            if client_id in self.clients:
                if self.host_client_id == client_id:
                    self.host_client_id = None
                del self.clients[client_id]

    def get_match_duration(self) -> int:
        with self.lock:
            return self.match_duration_seconds

    def set_match_duration(
        self,
        client_id: str,
        duration_seconds: int,
    ) -> bool:
        with self.lock:
            if (
                self.host_client_id is not None
                and client_id != self.host_client_id
            ):
                return False

            self.match_duration_seconds = coerce_match_duration(
                duration_seconds
            )
            return True

    def set_ready(self, client_id: str, ready: bool):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]["ready"] = ready

    def set_input(self, client_id: str, input_state: dict):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]["input"] = {
                    "up": bool(input_state.get("up", False)),
                    "down": bool(input_state.get("down", False)),
                    "left": bool(input_state.get("left", False)),
                    "right": bool(input_state.get("right", False)),
                }

    def get_snapshot(self):
        with self.lock:
            return {
                cid: {
                    "client_id": info["client_id"],
                    "name": info["name"],
                    "slot": info["slot"],
                    "team": info["team"],
                    "ready": info["ready"],
                    "input": dict(info["input"]),
                    "handler": info["handler"],
                }
                for cid, info in self.clients.items()
            }

    def export_public_state(self):
        with self.lock:
            exported = []
            for info in self.clients.values():
                exported.append(
                    {
                        "client_id": info["client_id"],
                        "name": info["name"],
                        "slot": info["slot"],
                        "team": info["team"],
                        "ready": info["ready"],
                    }
                )
            exported.sort(key=lambda x: x["slot"])
            return exported

    def get_handlers(self):
        with self.lock:
            return [info["handler"] for info in self.clients.values()]

    def get_host_name(self):
        with self.lock:
            if self.host_client_id is None:
                return None
            info = self.clients.get(self.host_client_id)
            if not info:
                return None
            return info.get("name")

    def can_start_match(self):
        with self.lock:
            if len(self.clients) < 2:
                return False
            return all(info["ready"] for info in self.clients.values())


class GameState:
    def __init__(
        self,
        lobby_snapshot: dict,
        match_duration_seconds: int = MATCH_DURATION_SECONDS,
        lobby_session_id: int | None = None,
    ):
        self.map_id = DEFAULT_MAP_ID
        self.layout = load_arena_layout(self.map_id)
        self.obstacle_rects = self.layout.collision_rects()
        self.lobby_session_id = lobby_session_id
        self.match_duration_seconds = coerce_match_duration(
            match_duration_seconds
        )
        self.started_at = time.time()
        self.ends_at = self.started_at + self.match_duration_seconds
        self.team_a_score = 0
        self.team_b_score = 0

        self.players = {}
        self.orbs = []
        self._spawn_players(lobby_snapshot)
        self._spawn_orbs()

    def _spawn_players(self, lobby_snapshot: dict):
        sorted_players = sorted(
            lobby_snapshot.items(),
            key=lambda item: item[1]["slot"],
        )

        players_by_team = {"A": [], "B": []}
        for client_id, info in sorted_players:
            players_by_team.setdefault(info["team"], []).append(
                (client_id, info)
            )

        for team_code, team_players in players_by_team.items():
            spawn_positions = get_team_spawn_positions(
                self.layout,
                team_code,
                len(team_players),
            )
            for index, (client_id, info) in enumerate(team_players):
                x, y = spawn_positions[index]

                self.players[client_id] = {
                    "client_id": client_id,
                    "slot": info["slot"],
                    "name": info["name"],
                    "team": info["team"],
                    "ready_at_start": bool(info.get("ready", False)),
                    "x": float(x),
                    "y": float(y),
                    "score": 0,
                    "disconnected": False,
                }

    def _spawn_orbs(self):
        self.orbs.clear()
        for _ in range(ORB_COUNT):
            self.orbs.append(self._random_orb())

    def _random_orb(self):
        x, y = random_free_point(
            self.layout,
            ORB_RADIUS,
            self.obstacle_rects,
            padding=20,
        )
        return {"x": x, "y": y}

    def update(self, dt: float, lobby_snapshot: dict):
        for client_id, player in self.players.items():
            if client_id not in lobby_snapshot:
                continue

            inp = lobby_snapshot[client_id]["input"]
            dx = 0
            dy = 0

            if inp["up"]:
                dy -= 1
            if inp["down"]:
                dy += 1
            if inp["left"]:
                dx -= 1
            if inp["right"]:
                dx += 1

            length = math.hypot(dx, dy)
            if length > 0:
                dx /= length
                dy /= length

            player["x"], player["y"] = resolve_movement(
                self.layout,
                player["x"],
                player["y"],
                dx * PLAYER_SPEED * dt,
                dy * PLAYER_SPEED * dt,
                PLAYER_RADIUS,
                self.obstacle_rects,
            )

        self._handle_orbs()

    def _handle_orbs(self):
        for player in self.players.values():
            for orb in self.orbs:
                dist = math.hypot(
                    player["x"] - orb["x"],
                    player["y"] - orb["y"],
                )
                if dist <= PLAYER_RADIUS + ORB_RADIUS:
                    player["score"] += 1
                    if player["team"] == "A":
                        self.team_a_score += 1
                    else:
                        self.team_b_score += 1

                    replacement = self._random_orb()
                    orb["x"] = replacement["x"]
                    orb["y"] = replacement["y"]

    def export_state(self):
        remaining = max(0, int(self.ends_at - time.time()))
        players = []
        for p in self.players.values():
            players.append(
                {
                    "client_id": p["client_id"],
                    "slot": p["slot"],
                    "name": p["name"],
                    "team": p["team"],
                    "x": round(p["x"], 1),
                    "y": round(p["y"], 1),
                    "score": p["score"],
                }
            )
        players.sort(key=lambda x: x["slot"])

        return {
            "type": STATE,
            "map_id": self.map_id,
            "arena_w": self.layout.width,
            "arena_h": self.layout.height,
            "arena_rect": list(self.layout.playable_rect),
            "obstacles": [list(rect) for rect in self.obstacle_rects],
            "duration_seconds": self.match_duration_seconds,
            "remaining_time": remaining,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "players": players,
            "orbs": list(self.orbs),
        }

    def is_finished(self):
        return time.time() >= self.ends_at

    def build_end_message(self):
        winner_team = get_winner_team(self.team_a_score, self.team_b_score)
        players = []

        for p in self.players.values():
            players.append(
                {
                    "slot": p["slot"],
                    "name": p["name"],
                    "team": p["team"],
                    "score": p["score"],
                }
            )

        players.sort(key=lambda item: item["slot"])

        return {
            "type": END,
            "winner_team": winner_team,
            "winner_text": format_winner_text(winner_team),
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "duration_seconds": self.match_duration_seconds,
            "players": players,
        }

    def build_persistable_result(self):
        winner_team = get_winner_team(self.team_a_score, self.team_b_score)

        players = []
        for p in self.players.values():
            players.append(
                {
                    "name": p["name"],
                    "team": p["team"],
                    "score": p["score"],
                    "slot_number": p["slot"],
                    "control_mode": "human",
                    "is_ai": False,
                    "ready_at_start": p.get("ready_at_start", False),
                }
            )

        return {
            "source_code": "LAN",
            "mode_code": "LAN",
            "arena_code": self.map_id,
            "lobby_session_id": self.lobby_session_id,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "winner_team": winner_team,
            "duration_seconds": self.match_duration_seconds,
            "started_at": datetime.fromtimestamp(self.started_at),
            "finished_at": datetime.now(),
            "players": players,
        }


class ArenaTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_class):
        self.hardware_service = None
        super().__init__(server_address, handler_class)
        self.lobby = LobbyState()
        self.lobby_invite_code = build_lobby_invite_code()
        self.lobby_session_id = None
        self.match_running = False
        self.game_state = None
        self.game_lock = threading.Lock()
        self.game_thread = None
        self.network_logger = LOGGER
        self.hardware_service = create_match_hardware_service()
        self.hardware_service.emit_state("LOBBY")
        self.hardware_service.emit_score(0, 0)

    def server_close(self):
        try:
            if self.hardware_service is not None:
                self.hardware_service.reset()
                self.hardware_service.shutdown()
        finally:
            super().server_close()

    def sync_lobby_persistence(self, status_code: str = "OPEN"):
        players = self.lobby.export_public_state()
        if not players:
            if self.lobby_session_id is not None:
                close_lobby_session(self.lobby_session_id)
                self.lobby_session_id = None
                self.lobby_invite_code = build_lobby_invite_code()
            return

        host_name = self.lobby.get_host_name()
        if self.lobby_session_id is None:
            self.lobby_session_id = open_lobby_session(
                host_name=host_name,
                invite_code=self.lobby_invite_code,
                match_duration_seconds=self.lobby.get_match_duration(),
                arena_code=DEFAULT_MAP_ID,
            )
            if self.lobby_session_id is None:
                return

        sync_lobby_session(
            self.lobby_session_id,
            players=players,
            match_duration_seconds=self.lobby.get_match_duration(),
            host_name=host_name,
            arena_code=DEFAULT_MAP_ID,
            status_code=status_code,
        )

    def broadcast(self, payload: dict):
        handlers = self.lobby.get_handlers()
        for handler in handlers:
            handler.safe_send(payload)

    def broadcast_lobby_state(self):
        payload = {
            "type": LOBBY_STATE,
            "players": self.lobby.export_public_state(),
            "match_duration_seconds": self.lobby.get_match_duration(),
        }
        self.broadcast(payload)

    def try_start_match(self):
        with self.game_lock:
            if self.match_running:
                return
            if not self.lobby.can_start_match():
                return

            snapshot = self.lobby.get_snapshot()
            self.sync_lobby_persistence(status_code="IN_MATCH")
            self.game_state = GameState(
                snapshot,
                self.lobby.get_match_duration(),
                lobby_session_id=self.lobby_session_id,
            )
            self.match_running = True
            self.network_logger.info(
                "Demarrage du match LAN (%s joueur(s), duree=%ss)",
                len(snapshot),
                self.lobby.get_match_duration(),
            )
            self.hardware_service.reset()
            self.hardware_service.emit_state("COMBAT")
            self.hardware_service.emit_score(0, 0)

            self.broadcast({"type": START})

            self.game_thread = threading.Thread(
                target=self.game_loop,
                daemon=True,
            )
            self.game_thread.start()

    def game_loop(self):
        dt = 1.0 / TICK_RATE
        next_tick = time.time()

        while self.match_running:
            snapshot = self.lobby.get_snapshot()

            if self.game_state is None:
                break

            self.game_state.update(dt, snapshot)
            self.hardware_service.emit_score(
                self.game_state.team_a_score,
                self.game_state.team_b_score,
            )
            self.broadcast(self.game_state.export_state())

            if self.game_state.is_finished():
                # sauvegarde DB du match réseau
                match_id = None
                save_error = None
                try:
                    match_result = self.game_state.build_persistable_result()
                    match_id = save_network_match_result(match_result)
                    self.network_logger.info(
                        "Match LAN sauvegarde en base (match_id=%s)",
                        match_id,
                    )
                except RuntimeError as error:
                    save_error = str(error)
                    self.network_logger.error(
                        "Erreur sauvegarde match LAN: %s",
                        error,
                    )

                end_message = self.game_state.build_end_message()
                end_message["history_saved"] = save_error is None
                end_message["match_id"] = match_id
                if save_error:
                    end_message["history_error"] = save_error

                self.hardware_service.emit_state("RESULT")
                self.hardware_service.emit_winner(
                    end_message.get("winner_team")
                )

                self.broadcast(end_message)

                with self.game_lock:
                    self.match_running = False
                    self.game_state = None

                for cid in list(snapshot.keys()):
                    self.lobby.set_ready(cid, False)

                self.sync_lobby_persistence(status_code="OPEN")
                self.broadcast_lobby_state()
                break

            next_tick += dt
            sleep_time = next_tick - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_tick = time.time()


class ArenaRequestHandler(socketserver.StreamRequestHandler):
    client_info = None

    def setup(self):
        super().setup()
        self.client_info = None
        self.send_lock = threading.Lock()

    def safe_send(self, message: dict):
        try:
            with self.send_lock:
                send_message_binary(self.wfile, message)
        except (BrokenPipeError, ConnectionError, OSError, ValueError):
            pass

    def handle_hello(self, message: dict):
        name = str(message.get("name", "")).strip()
        is_host = bool(message.get("host", False))
        if not name:
            self.safe_send({"type": ERROR, "message": "Nom vide refusé."})
            return False

        info = self.server.lobby.add_client(
            name=name,
            handler=self,
            is_host=is_host,
        )
        if info is None:
            self.safe_send(
                {"type": ERROR, "message": "Serveur plein (6 joueurs max)."}
            )
            return False

        self.client_info = info
        remote_ip, remote_port = self.client_address
        self.server.network_logger.info(
            "Client LAN connecte: %s (%s:%s, slot=%s, team=%s, host=%s)",
            info["name"],
            remote_ip,
            remote_port,
            info["slot"],
            info["team"],
            is_host,
        )

        self.safe_send(
            {
                "type": ASSIGN_SLOT,
                "client_id": info["client_id"],
                "slot": info["slot"],
                "team": info["team"],
                "name": info["name"],
            }
        )

        self.server.sync_lobby_persistence(status_code="OPEN")
        self.server.broadcast_lobby_state()
        return True

    def handle(self):
        try:
            hello = receive_message_binary(self.rfile)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            self.server.network_logger.warning(
                "HELLO LAN illisible depuis %s:%s: %s",
                self.client_address[0],
                self.client_address[1],
                error,
            )
            self.safe_send(
                {
                    "type": ERROR,
                    "message": "Le message d'ouverture du hall est invalide.",
                }
            )
            return
        except OSError as error:
            self.server.network_logger.info(
                "Connexion fermee avant HELLO depuis %s:%s: %s",
                self.client_address[0],
                self.client_address[1],
                error,
            )
            return

        if hello is None:
            return

        if hello.get("type") != HELLO:
            self.safe_send(
                {
                    "type": ERROR,
                    "message": "Le premier message doit être HELLO.",
                }
            )
            return

        if not self.handle_hello(hello):
            return

        while True:
            try:
                message = receive_message_binary(self.rfile)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                self.server.network_logger.warning(
                    "Message LAN illisible depuis %s:%s: %s",
                    self.client_address[0],
                    self.client_address[1],
                    error,
                )
                self.safe_send(
                    {
                        "type": ERROR,
                        "message": (
                            "Un message reseau recu par le hall est invalide."
                        ),
                    }
                )
                break
            except OSError as error:
                self.server.network_logger.info(
                    "Connexion LAN interrompue depuis %s:%s: %s",
                    self.client_address[0],
                    self.client_address[1],
                    error,
                )
                break

            if message is None:
                break

            msg_type = message.get("type")

            if msg_type == READY:
                ready = bool(message.get("ready", False))
                self.server.lobby.set_ready(
                    self.client_info["client_id"],
                    ready,
                )
                self.server.sync_lobby_persistence(status_code="OPEN")
                self.server.broadcast_lobby_state()
                self.server.try_start_match()

            elif msg_type == INPUT:
                self.server.lobby.set_input(
                    self.client_info["client_id"],
                    {
                        "up": message.get("up", False),
                        "down": message.get("down", False),
                        "left": message.get("left", False),
                        "right": message.get("right", False),
                    },
                )

            elif msg_type == PING:
                self.safe_send({"type": PONG})

            elif msg_type == REQUEST_HISTORY:
                self.server.network_logger.info(
                    "Chroniques LAN demandees par %s",
                    self.client_info["name"],
                )
                rows = get_serializable_match_history()
                self.safe_send(
                    {"type": HISTORY_DATA, "ok": True, "rows": rows}
                )

            elif msg_type == SET_MATCH_DURATION:
                requested_duration = message.get(
                    "duration_seconds",
                    MATCH_DURATION_SECONDS,
                )
                if not self.server.lobby.set_match_duration(
                    self.client_info["client_id"],
                    requested_duration,
                ):
                    self.safe_send(
                        {
                            "type": ERROR,
                            "message": (
                                "Seul le gardien du hall peut régler la durée "
                                "de la joute."
                            ),
                        }
                    )
                    self.server.network_logger.warning(
                        "Refus changement duree LAN pour %s",
                        self.client_info["name"],
                    )
                else:
                    self.server.sync_lobby_persistence(status_code="OPEN")
                    self.server.broadcast_lobby_state()
                    self.server.network_logger.info(
                        "Duree LAN mise a jour a %ss par %s",
                        self.server.lobby.get_match_duration(),
                        self.client_info["name"],
                    )

            else:
                self.safe_send(
                    {"type": ERROR, "message": f"Message inconnu: {msg_type}"}
                )

    def finish(self):
        if self.client_info is not None:
            self.server.network_logger.info(
                "Client LAN deconnecte: %s",
                self.client_info["name"],
            )
            self.server.lobby.remove_client(self.client_info["client_id"])
            self.server.sync_lobby_persistence(status_code="OPEN")
            self.server.broadcast_lobby_state()
        super().finish()


def run_server(host: str, port: int):
    try:
        server = ArenaTCPServer((host, port), ArenaRequestHandler)
    except OSError as error:
        raise RuntimeError(format_bind_error(host, port, error)) from error

    with server:
        address_info = get_lan_address_info()
        invite_endpoint = (
            format_endpoint(address_info.primary_ip, port)
            if address_info.primary_ip
            else "IP LAN indisponible"
        )
        LOGGER.info(
            "Serveur LAN en ecoute sur %s",
            format_endpoint(host, port),
        )
        LOGGER.info("Invitation LAN conseillee: %s", invite_endpoint)
        if address_info.warning:
            LOGGER.warning(address_info.warning)
        server.serve_forever()


def start_server_in_background(host: str = "0.0.0.0", port: int = 5000):
    try:
        server = ArenaTCPServer((host, port), ArenaRequestHandler)
    except OSError as error:
        raise RuntimeError(format_bind_error(host, port, error)) from error

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    address_info = get_lan_address_info()
    invite_endpoint = (
        format_endpoint(address_info.primary_ip, port)
        if address_info.primary_ip
        else "IP LAN indisponible"
    )
    LOGGER.info(
        "Serveur LAN lance en arriere-plan sur %s",
        format_endpoint(host, port),
    )
    LOGGER.info("Invitation LAN conseillee: %s", invite_endpoint)
    if address_info.warning:
        LOGGER.warning(address_info.warning)

    return server, thread, address_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arena Duel - serveur LAN")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP d'écoute du serveur",
    )
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    args = parser.parse_args()

    try:
        run_server(args.host, args.port)
    except RuntimeError as error:
        print(f"[server] {error}")
        raise SystemExit(1) from error
