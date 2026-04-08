import argparse
import json
import queue
import socket
import threading
import time

from network.messages import (
    DISCONNECTED,
    ERROR,
    HELLO,
    INPUT,
    PING,
    READY,
    REQUEST_HISTORY,
    SET_MATCH_DURATION,
)
from network.protocol import encode_message, decode_message


class NetworkClient:
    def __init__(self):
        self.sock = None
        self.running = False
        self.reader_thread = None
        self.incoming = queue.Queue()
        self.send_lock = threading.Lock()
        self.disconnect_notified = False

        self.last_input_state = None
        self.last_input_send_time = 0.0

    def connect(self, host: str, port: int, name: str, is_host: bool = False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.running = True
        self.disconnect_notified = False
        self.last_input_state = None
        self.last_input_send_time = 0.0

        if not self.send({"type": HELLO, "name": name, "host": is_host}):
            self.close()
            raise ConnectionError(
                "Impossible d'initialiser la session réseau."
            )

        self.reader_thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )
        self.reader_thread.start()

    def _close_socket(self):
        sock = self.sock
        self.sock = None

        if sock is None:
            return

        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            sock.close()
        except OSError:
            pass

    def _notify_disconnect(self, message: str):
        if self.disconnect_notified:
            return

        self.disconnect_notified = True
        self.running = False
        self.incoming.put(
            {
                "type": DISCONNECTED,
                "message": message,
            }
        )

    def _reader_loop(self):
        buffer = b""
        try:
            while self.running:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break

                buffer += chunk

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            message = decode_message(line + b"\n")
                            if message is not None:
                                self.incoming.put(message)
                        except (
                            json.JSONDecodeError,
                            UnicodeDecodeError,
                        ) as error:
                            self.incoming.put(
                                {
                                    "type": "ERROR",
                                    "message": (
                                        f"Décodage impossible: {error}"
                                    ),
                                }
                            )
        except OSError as error:
            self.incoming.put(
                {
                    "type": ERROR,
                    "message": f"Lecture réseau impossible: {error}",
                }
            )
        finally:
            self.running = False
            self._close_socket()
            self._notify_disconnect("Connexion fermée.")

    def send(self, message: dict):
        if not self.sock or not self.running:
            return False

        data = encode_message(message)
        try:
            with self.send_lock:
                self.sock.sendall(data)
            return True
        except OSError as error:
            self.incoming.put(
                {
                    "type": ERROR,
                    "message": f"Envoi réseau impossible: {error}",
                }
            )
            self._close_socket()
            self._notify_disconnect(
                "Connexion perdue pendant l'envoi des données."
            )
            return False

    def send_ready(self, ready: bool):
        self.send({"type": READY, "ready": ready})

    def send_ping(self):
        self.send({"type": PING})

    def send_request_history(self):
        return self.send({"type": REQUEST_HISTORY})

    def send_match_duration(self, duration_seconds: int):
        return self.send(
            {
                "type": SET_MATCH_DURATION,
                "duration_seconds": duration_seconds,
            }
        )

    def send_input(self, up: bool, down: bool, left: bool, right: bool):
        now = time.time()

        state = {
            "up": up,
            "down": down,
            "left": left,
            "right": right,
        }

        # envoyer seulement si l'état change
        # ou au moins toutes les 100 ms pour garder la synchro propre
        if (
            state != self.last_input_state
            or (now - self.last_input_send_time) >= 0.1
        ):
            self.send(
                {
                    "type": INPUT,
                    "up": up,
                    "down": down,
                    "left": left,
                    "right": right,
                }
            )
            self.last_input_state = state
            self.last_input_send_time = now

    def poll_messages(self):
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages

    def close(self):
        self.running = False
        self._close_socket()


def run_cli_client(host: str, port: int, name: str):
    client = NetworkClient()
    client.connect(host, port, name)

    print(f"[client] connecté à {host}:{port} en tant que {name}")
    print("[client] commandes : /ready on | /ready off | /ping | /quit")

    try:
        while client.running:
            for msg in client.poll_messages():
                print(f"[recv] {msg}")

            user_input = input("> ").strip()

            if user_input == "/quit":
                break
            elif user_input == "/ping":
                client.send_ping()
            elif user_input == "/ready on":
                client.send_ready(True)
            elif user_input == "/ready off":
                client.send_ready(False)
            elif user_input:
                print("Commande inconnue.")
    finally:
        client.close()
        print("[client] fermeture")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arena Duel - client LAN")
    parser.add_argument("--host", required=True, help="IP du serveur")
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    parser.add_argument("--name", required=True, help="Nom du joueur")
    args = parser.parse_args()

    run_cli_client(args.host, args.port, args.name)
