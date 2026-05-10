import argparse
import json
import queue
import socket
import sys
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
    REQUEST_TELEMETRY,
    SET_MATCH_DURATION,
)
from network.net_utils import (
    format_connect_error,
    format_endpoint,
    get_network_logger,
    load_lan_runtime_config,
    parse_server_invitation,
)
from network.protocol import encode_message


class NetworkClient:
    def __init__(self):
        self.sock = None
        self.running = False
        self.reader_thread = None
        self.incoming = queue.Queue()
        self.send_lock = threading.Lock()
        self.disconnect_notified = False
        self.logger = get_network_logger()

        self.last_input_state = None
        self.last_input_send_time = 0.0

    def connect_with_retry(
        self,
        host: str,
        port: int,
        name: str,
        is_host: bool = False,
        spectator: bool = False,
        timeout_seconds: float | None = None,
        sprite_id: str | None = None,
        max_retries: int = 5,
        initial_delay_seconds: float = 1.0,
    ):
        """Connect with exponential backoff retry (1s, 2s, 4s, 8s, 16s)"""
        delay = initial_delay_seconds
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self.connect(
                    host=host,
                    port=port,
                    name=name,
                    is_host=is_host,
                    spectator=spectator,
                    timeout_seconds=timeout_seconds,
                    sprite_id=sprite_id,
                )
                self.logger.info("Reconnexion reussie apres %d tentative(s)", attempt)
                return  # Success
            except ConnectionError as error:
                last_error = error
                if attempt < max_retries:
                    self.logger.warning(
                        "Tentative de connexion %d/%d echouee. "
                        "Nouvelle tentative dans %fs...",
                        attempt,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 32.0)  # Cap at 32 seconds
                else:
                    self.logger.error(
                        "Toutes les %d tentatives de connexion ont echoue",
                        max_retries,
                    )

        if last_error:
            raise last_error
        raise ConnectionError("Impossible de se connecter au serveur LAN")

    def connect(
        self,
        host: str,
        port: int,
        name: str,
        is_host: bool = False,
        spectator: bool = False,
        timeout_seconds: float | None = None,
        sprite_id: str | None = None,
    ):
        socket_timeout = (
            timeout_seconds or load_lan_runtime_config().connect_timeout_seconds
        )
        endpoint = format_endpoint(host, port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(socket_timeout)
        self.logger.info(
            "Tentative de connexion LAN vers %s (joueur=%s, host_mode=%s)",
            endpoint,
            name,
            is_host,
        )

        try:
            sock.connect((host, port))
            sock.settimeout(None)
        except OSError as error:
            try:
                sock.close()
            except OSError:
                pass
            self.logger.warning(
                "Connexion LAN echouee vers %s: %s",
                endpoint,
                error,
            )
            raise ConnectionError(format_connect_error(host, port, error)) from error

        self.sock = sock
        self.running = True
        self.disconnect_notified = False
        self.last_input_state = None
        self.last_input_send_time = 0.0

        hello_payload = {
            "type": HELLO,
            "name": name,
            "host": is_host,
        }
        if spectator:
            hello_payload["spectator"] = True
        normalized_sprite_id = str(sprite_id or "").strip()
        if normalized_sprite_id:
            hello_payload["sprite_id"] = normalized_sprite_id

        if not self.send(hello_payload):
            self.close()
            self.logger.error(
                "Initialisation LAN echouee apres connexion vers %s",
                endpoint,
            )
            raise ConnectionError("Impossible d'initialiser la session réseau.")

        self.reader_thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
        )
        self.reader_thread.start()
        self.logger.info("Connexion LAN etablie vers %s", endpoint)

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
        self.logger.info("Connexion LAN fermee: %s", message)
        self.incoming.put(
            {
                "type": DISCONNECTED,
                "message": message,
            }
        )

    def _reader_loop(self):
        """Read messages using robust length-prefixed protocol"""
        import struct

        MAX_BUFFER_SIZE = 64 * 1024 * 1024  # 64MB hard limit
        buffer = b""
        try:
            while self.running:
                # Check buffer size
                if len(buffer) > MAX_BUFFER_SIZE:
                    self.logger.warning(
                        "Buffer reseau depasse la limite (%d bytes)", len(buffer)
                    )
                    self.incoming.put(
                        {
                            "type": ERROR,
                            "message": "Buffer overflow: message too large",
                        }
                    )
                    break

                # Try to read 4-byte header for message length
                while len(buffer) < 4 and self.running:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        self.logger.info("Le serveur LAN a ferme le flux TCP.")
                        self.running = False
                        break
                    buffer += chunk

                if not self.running or len(buffer) < 4:
                    break

                # Parse message length
                try:
                    message_size = struct.unpack("!I", buffer[:4])[0]
                except struct.error as error:
                    self.logger.warning("En-tete de message invalide: %s", error)
                    self.incoming.put(
                        {
                            "type": ERROR,
                            "message": f"Protocol error: {error}",
                        }
                    )
                    break

                if message_size <= 0 or message_size > 1024 * 1024:
                    self.logger.warning(
                        "Taille de message LAN invalide: %d", message_size
                    )
                    self.incoming.put(
                        {
                            "type": ERROR,
                            "message": f"Message size invalid: {message_size}",
                        }
                    )
                    break

                # Read full message payload
                while len(buffer) < 4 + message_size and self.running:
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        self.logger.info("Le serveur LAN a ferme le flux TCP.")
                        self.running = False
                        break
                    buffer += chunk

                if not self.running or len(buffer) < 4 + message_size:
                    break

                # Extract and parse message
                payload = buffer[4 : 4 + message_size]
                buffer = buffer[4 + message_size :]

                try:
                    message = json.loads(payload.decode("utf-8"))
                    if message is not None:
                        self.incoming.put(message)
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    self.logger.warning(
                        "Message LAN illisible recu: %s",
                        error,
                    )
                    self.incoming.put(
                        {
                            "type": ERROR,
                            "message": f"Décodage impossible: {error}",
                        }
                    )

        except OSError as error:
            if self.running:
                self.logger.warning("Lecture LAN interrompue: %s", error)
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
            self.logger.warning(
                "Envoi LAN impossible (%s): %s",
                message.get("type", "?"),
                error,
            )
            self.incoming.put(
                {
                    "type": ERROR,
                    "message": f"Envoi réseau impossible: {error}",
                }
            )
            self._close_socket()
            self._notify_disconnect("Connexion perdue pendant l'envoi des données.")
            return False

    def send_ready(self, ready: bool):
        return self.send({"type": READY, "ready": ready})

    def send_ping(self):
        self.send({"type": PING})

    def send_request_history(self):
        return self.send({"type": REQUEST_HISTORY})

    def send_request_telemetry(self):
        return self.send({"type": REQUEST_TELEMETRY})

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
        if state != self.last_input_state or (now - self.last_input_send_time) >= 0.1:
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
        self.logger.info("Client LAN ferme localement.")


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
    parser.add_argument(
        "--server",
        help="Invitation LAN au format IP:port ou IP",
    )
    parser.add_argument("--host", help="IP du serveur")
    parser.add_argument("--port", type=int, default=5000, help="Port TCP")
    parser.add_argument("--name", required=True, help="Nom du joueur")
    args = parser.parse_args()

    if args.server:
        resolved_host, resolved_port = parse_server_invitation(
            args.server,
            args.port,
        )
    else:
        if not args.host:
            parser.error("Utilise --server ou --host pour cibler un hall LAN.")
        resolved_host, resolved_port = args.host, args.port

    try:
        run_cli_client(resolved_host, resolved_port, args.name)
    except ConnectionError as error:
        print(f"[client] connexion impossible: {error}")
        sys.exit(1)
