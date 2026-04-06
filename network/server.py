import argparse
import socketserver
import threading
import uuid

from network.messages import (
    HELLO,
    ASSIGN_SLOT,
    LOBBY_STATE,
    READY,
    PING,
    PONG,
    ERROR,
)
from network.protocol import send_message_binary, receive_message_binary


MAX_PLAYERS = 6


def slot_to_team(slot: int) -> str:
    # Slots 1..3 = équipe A, 4..6 = équipe B
    return "A" if slot <= 3 else "B"


class LobbyState:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = {}  # client_id -> info dict

    def get_used_slots(self) -> set[int]:
        return {info["slot"] for info in self.clients.values()}

    def get_next_free_slot(self) -> int | None:
        used = self.get_used_slots()
        for slot in range(1, MAX_PLAYERS + 1):
            if slot not in used:
                return slot
        return None

    def add_client(self, name: str, handler) -> dict | None:
        with self.lock:
            if len(self.clients) >= MAX_PLAYERS:
                return None

            slot = self.get_next_free_slot()
            if slot is None:
                return None

            client_id = str(uuid.uuid4())[:8]
            info = {
                "client_id": client_id,
                "name": name,
                "slot": slot,
                "team": slot_to_team(slot),
                "ready": False,
                "handler": handler,
            }
            self.clients[client_id] = info
            return info

    def remove_client(self, client_id: str) -> None:
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]

    def set_ready(self, client_id: str, ready: bool) -> None:
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id]["ready"] = ready

    def export_public_state(self) -> list[dict]:
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


class ArenaTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_class):
        super().__init__(server_address, handler_class)
        self.lobby = LobbyState()

    def broadcast_lobby_state(self):
        payload = {
            "type": LOBBY_STATE,
            "players": self.lobby.export_public_state(),
        }
        handlers = self.lobby.get_handlers()
        for handler in handlers:
            handler.safe_send(payload)


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
            # Le client a probablement déjà coupé
            pass

    def handle_hello(self, message: dict):
        name = str(message.get("name", "")).strip()
        if not name:
            self.safe_send(
                {
                    "type": ERROR,
                    "message": "Nom vide refusé.",
                }
            )
            return False

        info = self.server.lobby.add_client(name=name, handler=self)
        if info is None:
            self.safe_send(
                {
                    "type": ERROR,
                    "message": "Serveur plein (6 joueurs max).",
                }
            )
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
        # 1) le premier message attendu = HELLO
        hello = receive_message_binary(self.rfile)
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

        # 2) boucle principale de réception
        while True:
            message = receive_message_binary(self.rfile)
            if message is None:
                break

            msg_type = message.get("type")

            if msg_type == READY:
                ready = bool(message.get("ready", False))
                self.server.lobby.set_ready(self.client_info["client_id"], ready)
                self.server.broadcast_lobby_state()

            elif msg_type == PING:
                self.safe_send({"type": PONG})

            else:
                self.safe_send(
                    {
                        "type": ERROR,
                        "message": f"Message inconnu: {msg_type}",
                    }
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
    parser = argparse.ArgumentParser(description="Arena Duel - serveur LAN (phase 1)")
    parser.add_argument("--host", default="0.0.0.0", help="IP d'écoute du serveur")
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    args = parser.parse_args()

    run_server(args.host, args.port)