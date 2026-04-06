import argparse
import math
import random
import socketserver
import threading
import time
import uuid

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
)
from network.protocol import send_message_binary, receive_message_binary
from db.network_match_repository import save_network_match_result

MAX_PLAYERS = 6

ARENA_W = 1280
ARENA_H = 720
PLAYER_RADIUS = 18
PLAYER_SPEED = 260
ORB_RADIUS = 10
ORB_COUNT = 12

MATCH_SECONDS = 60
TICK_RATE = 20



def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


class LobbyState:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = {}  # client_id -> info

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

    def add_client(self, name: str, handler):
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
                "ready": False,
                "handler": handler,
                "input": {"up": False, "down": False, "left": False, "right": False},
            }
            self.clients[client_id] = info
            return info


    def remove_client(self, client_id: str):
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]

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

    def can_start_match(self):
        with self.lock:
            if len(self.clients) < 2:
                return False
            return all(info["ready"] for info in self.clients.values())


class GameState:
    def __init__(self, lobby_snapshot: dict):
        self.started_at = time.time()
        self.ends_at = self.started_at + MATCH_SECONDS
        self.team_a_score = 0
        self.team_b_score = 0

        self.players = {}
        self.orbs = []
        self._spawn_players(lobby_snapshot)
        self._spawn_orbs()

    def _spawn_players(self, lobby_snapshot: dict):
        team_spawns = {
            "A": [(120, 180), (120, 360), (120, 540)],
            "B": [(1160, 180), (1160, 360), (1160, 540)],
        }

        team_indexes = {"A": 0, "B": 0}

        # tri par slot pour garder un ordre stable
        sorted_players = sorted(
            lobby_snapshot.items(),
            key=lambda item: item[1]["slot"]
        )

        for client_id, info in sorted_players:
            team = info["team"]
            index = team_indexes.get(team, 0)

            spawn_list = team_spawns.get(team, [(100, 100)])
            if index >= len(spawn_list):
                index = len(spawn_list) - 1

            x, y = spawn_list[index]
            team_indexes[team] += 1

            self.players[client_id] = {
                "client_id": client_id,
                "slot": info["slot"],
                "name": info["name"],
                "team": info["team"],
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
        return {
            "x": random.randint(200, ARENA_W - 200),
            "y": random.randint(80, ARENA_H - 80),
        }

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

            player["x"] += dx * PLAYER_SPEED * dt
            player["y"] += dy * PLAYER_SPEED * dt

            player["x"] = clamp(player["x"], PLAYER_RADIUS, ARENA_W - PLAYER_RADIUS)
            player["y"] = clamp(player["y"], PLAYER_RADIUS, ARENA_H - PLAYER_RADIUS)

        self._handle_orbs()

    def _handle_orbs(self):
        for player in self.players.values():
            for orb in self.orbs:
                dist = math.hypot(player["x"] - orb["x"], player["y"] - orb["y"])
                if dist <= PLAYER_RADIUS + ORB_RADIUS:
                    player["score"] += 1
                    if player["team"] == "A":
                        self.team_a_score += 1
                    else:
                        self.team_b_score += 1

                    orb["x"] = random.randint(200, ARENA_W - 200)
                    orb["y"] = random.randint(80, ARENA_H - 80)

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
            "arena_w": ARENA_W,
            "arena_h": ARENA_H,
            "remaining_time": remaining,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "players": players,
            "orbs": list(self.orbs),
        }

    def is_finished(self):
        return time.time() >= self.ends_at

    def build_end_message(self):
        if self.team_a_score > self.team_b_score:
            winner = "Victoire Équipe A"
        elif self.team_b_score > self.team_a_score:
            winner = "Victoire Équipe B"
        else:
            winner = "Match nul"

        return {
            "type": END,
            "winner_text": winner,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
        }
    
    
    def build_persistable_result(self):
        if self.team_a_score > self.team_b_score:
            winner_team = "A"
        elif self.team_b_score > self.team_a_score:
            winner_team = "B"
        else:
            winner_team = "DRAW"

        players = []
        for p in self.players.values():
            players.append(
                {
                    "name": p["name"],
                    "team": p["team"],
                    "score": p["score"],
                }
            )

        return {
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "winner_team": winner_team,
            "duration_seconds": MATCH_SECONDS,
            "players": players,
        }



class ArenaTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self.lobby = LobbyState()
        self.match_running = False
        self.game_state = None
        self.game_lock = threading.Lock()
        self.game_thread = None

    def broadcast(self, payload: dict):
        handlers = self.lobby.get_handlers()
        for handler in handlers:
            handler.safe_send(payload)

    def broadcast_lobby_state(self):
        payload = {
            "type": LOBBY_STATE,
            "players": self.lobby.export_public_state(),
        }
        self.broadcast(payload)

    def try_start_match(self):
        with self.game_lock:
            if self.match_running:
                return
            if not self.lobby.can_start_match():
                return

            snapshot = self.lobby.get_snapshot()
            self.game_state = GameState(snapshot)
            self.match_running = True

            self.broadcast({"type": START})

            self.game_thread = threading.Thread(target=self.game_loop, daemon=True)
            self.game_thread.start()

    def game_loop(self):
        dt = 1.0 / TICK_RATE
        next_tick = time.time()

        while self.match_running:
            snapshot = self.lobby.get_snapshot()

            if self.game_state is None:
                break

            self.game_state.update(dt, snapshot)
            self.broadcast(self.game_state.export_state())

            if self.game_state.is_finished():
                end_message = self.game_state.build_end_message()
                self.broadcast(end_message)

                # sauvegarde DB du match réseau
                try:
                    match_result = self.game_state.build_persistable_result()
                    match_id = save_network_match_result(match_result)
                    print(f"[server] match LAN sauvegardé en base (match_id={match_id})")
                except Exception as e:
                    print(f"[server] erreur sauvegarde match LAN: {e}")

                with self.game_lock:
                    self.match_running = False
                    self.game_state = None

                for cid in list(snapshot.keys()):
                    self.lobby.set_ready(cid, False)

                self.broadcast_lobby_state()
                break

            next_tick += dt
            sleep_time = next_tick - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_tick = time.time()

class ArenaRequestHandler(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.client_info = None
        self.send_lock = threading.Lock()

    def safe_send(self, message: dict):
        try:
            with self.send_lock:
                send_message_binary(self.wfile, message)
        except Exception:
            pass

    def handle_hello(self, message: dict):
        name = str(message.get("name", "")).strip()
        if not name:
            self.safe_send({"type": ERROR, "message": "Nom vide refusé."})
            return False

        info = self.server.lobby.add_client(name=name, handler=self)
        if info is None:
            self.safe_send({"type": ERROR, "message": "Serveur plein (6 joueurs max)."})
            return False

        self.client_info = info

        self.safe_send(
            {
                "type": ASSIGN_SLOT,
                "client_id": info["client_id"],
                "slot": info["slot"],
                "team": info["team"],
                "name": info["name"],
            }
        )

        self.server.broadcast_lobby_state()
        return True

    def handle(self):
        hello = receive_message_binary(self.rfile)
        if hello is None:
            return

        if hello.get("type") != HELLO:
            self.safe_send(
                {"type": ERROR, "message": "Le premier message doit être HELLO."}
            )
            return

        if not self.handle_hello(hello):
            return

        while True:
            message = receive_message_binary(self.rfile)
            if message is None:
                break

            msg_type = message.get("type")

            if msg_type == READY:
                ready = bool(message.get("ready", False))
                self.server.lobby.set_ready(self.client_info["client_id"], ready)
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

            else:
                self.safe_send(
                    {"type": ERROR, "message": f"Message inconnu: {msg_type}"}
                )

    def finish(self):
        try:
            if self.client_info is not None:
                self.server.lobby.remove_client(self.client_info["client_id"])
                self.server.broadcast_lobby_state()
        except Exception:
            pass
        super().finish()


def run_server(host: str, port: int):
    with ArenaTCPServer((host, port), ArenaRequestHandler) as server:
        print(f"[server] écoute sur {host}:{port}")
        print("[server] Ctrl+C pour arrêter")
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arena Duel - serveur LAN")
    parser.add_argument("--host", default="0.0.0.0", help="IP d'écoute du serveur")
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    args = parser.parse_args()

    run_server(args.host, args.port)