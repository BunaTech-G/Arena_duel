import argparse
import queue
import socket
import threading

from network.messages import HELLO, READY, PING
from network.protocol import encode_message, decode_message


class NetworkClient:
    def __init__(self):
        self.sock = None
        self.running = False
        self.reader_thread = None
        self.incoming = queue.Queue()
        self.send_lock = threading.Lock()

    def connect(self, host: str, port: int, name: str):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.running = True

        # Envoi du HELLO
        self.send({"type": HELLO, "name": name})

        # Démarrage du thread de lecture
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

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
                        except Exception as e:
                            self.incoming.put(
                                {
                                    "type": "ERROR",
                                    "message": f"Décodage impossible: {e}",
                                }
                            )
        except Exception as e:
            self.incoming.put(
                {
                    "type": "ERROR",
                    "message": f"Lecture réseau impossible: {e}",
                }
            )
        finally:
            self.running = False
            self.incoming.put(
                {
                    "type": "DISCONNECTED",
                    "message": "Connexion fermée.",
                }
            )

    def send(self, message: dict):
        if not self.sock or not self.running:
            return

        data = encode_message(message)
        with self.send_lock:
            self.sock.sendall(data)

    def send_ready(self, ready: bool):
        self.send({"type": READY, "ready": ready})

    def send_ping(self):
        self.send({"type": PING})

    def poll_messages(self) -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages

    def close(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass


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
    parser = argparse.ArgumentParser(description="Arena Duel - client LAN (phase 1)")
    parser.add_argument("--host", required=True, help="IP du serveur")
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    parser.add_argument("--name", required=True, help="Nom du joueur")
    args = parser.parse_args()

    run_cli_client(args.host, args.port, args.name)