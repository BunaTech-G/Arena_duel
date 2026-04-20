from __future__ import annotations

import contextlib
from dataclasses import dataclass
import errno
import json
import queue
import re
import socket
import struct
import subprocess
import threading
import time
import unicodedata

from network.net_utils import format_endpoint, get_network_logger


PROTO_VERSION = 1
DEFAULT_ONLINE_HOST = "165.227.166.21"
DEFAULT_ONLINE_PORT = 27015
DEFAULT_ONLINE_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_ONLINE_PROBE_TIMEOUT_SECONDS = 0.45
DEFAULT_ONLINE_NETSH_TIMEOUT_SECONDS = 1.2
ONLINE_READ_TIMEOUT_SECONDS = 0.5
MAX_ONLINE_MESSAGE_BYTES = 1024 * 1024
ONLINE_HEARTBEAT_INTERVAL_SECONDS = 10.0
ONLINE_HEARTBEAT_TIMEOUT_SECONDS = 30.0
ONLINE_NETWORK_GOOD_LATENCY_MS = 180

LOGGER = get_network_logger()


class OnlineClientError(RuntimeError):
    pass


class OnlineConnectionError(OnlineClientError):
    pass


class OnlineProtocolError(OnlineClientError):
    pass


@dataclass(frozen=True)
class OnlineNetworkStatus:
    transport_kind: str
    transport_label: str
    tone: str
    signal_bars: int
    online_available: bool
    is_connected: bool
    quality_label: str
    latency_ms: int | None = None


def _format_connect_error(host: str, port: int, error: OSError) -> str:
    endpoint = format_endpoint(host, port)
    winerror = getattr(error, "winerror", None)
    error_code = getattr(error, "errno", None)

    if isinstance(error, socket.gaierror):
        return f"Adresse invalide ou introuvable pour le serveur online: {endpoint}."

    if (
        isinstance(error, TimeoutError)
        or error_code == errno.ETIMEDOUT
        or winerror == 10060
    ):
        return (
            f"Serveur online injoignable sur {endpoint}. "
            "Verifie l'hote, le port et la connexion Internet."
        )

    if (
        isinstance(error, ConnectionRefusedError)
        or error_code == errno.ECONNREFUSED
        or winerror == 10061
    ):
        return f"Le serveur online a refuse la connexion sur {endpoint}."

    if error_code in {errno.EHOSTUNREACH, errno.ENETUNREACH} or winerror in {
        10051,
        10065,
    }:
        return f"Le serveur online {endpoint} n'est pas joignable depuis ce poste."

    return f"Connexion impossible vers {endpoint}: {error}."


def _format_runtime_error(error: BaseException) -> str:
    if isinstance(error, OnlineProtocolError):
        return str(error)

    if isinstance(error, json.JSONDecodeError):
        return "Le serveur online a renvoye un JSON invalide."

    if isinstance(error, UnicodeDecodeError):
        return "Le serveur online a renvoye une reponse non UTF-8."

    if isinstance(error, ConnectionResetError):
        return "Connexion interrompue par le serveur online."

    if isinstance(error, ConnectionAbortedError):
        return "Connexion online fermee localement."

    if isinstance(error, BrokenPipeError):
        return "Connexion online coupee pendant l'envoi."

    if isinstance(error, TimeoutError):
        return "Le serveur online ne repond plus."

    if isinstance(error, OSError):
        winerror = getattr(error, "winerror", None)
        error_code = getattr(error, "errno", None)
        if error_code == errno.ECONNRESET or winerror == 10054:
            return "Connexion interrompue par le serveur online."
        if error_code == errno.ENOTCONN or winerror == 10057:
            return "Connexion online perdue."
        return f"Erreur reseau online: {error}."

    return f"Erreur online inattendue: {error}."


def _normalize_network_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower()


def _classify_interface_name(interface_name: str) -> str:
    normalized_name = _normalize_network_text(interface_name)
    if any(token in normalized_name for token in ("wi-fi", "wifi", "wlan", "wireless")):
        return "wifi"

    if any(
        token in normalized_name
        for token in ("ethernet", "local area", "local connection", "lan")
    ):
        return "ethernet"

    return "network"


def _transport_label(transport_kind: str) -> str:
    if transport_kind == "ethernet":
        return "Ethernet"
    if transport_kind == "wifi":
        return "Wi-Fi"
    if transport_kind == "offline":
        return "Hors ligne"
    return "Réseau"


def _run_netsh_interface_listing() -> str:
    try:
        completed = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=DEFAULT_ONLINE_NETSH_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""

    return str(completed.stdout or "")


def _connected_interface_kinds() -> list[str]:
    output = _run_netsh_interface_listing()
    interface_kinds: list[str] = []

    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        normalized_line = _normalize_network_text(stripped)
        if not normalized_line:
            continue
        if "admin" in normalized_line and "type" in normalized_line:
            continue
        if set(normalized_line) == {"-"}:
            continue

        parts = re.split(r"\s{2,}", stripped, maxsplit=3)
        if len(parts) < 4:
            continue

        admin_state, state, _interface_type, interface_name = parts
        normalized_admin_state = _normalize_network_text(admin_state)
        normalized_state = _normalize_network_text(state)

        if not normalized_admin_state.startswith(("activ", "enabl")):
            continue
        if normalized_state.startswith(("deconnect", "dconnect", "disconnect")):
            continue
        if not normalized_state.startswith(("connect", "link")):
            continue

        interface_kinds.append(_classify_interface_name(interface_name))

    return interface_kinds


def _primary_interface_kind() -> str | None:
    interface_kinds = _connected_interface_kinds()
    if not interface_kinds:
        return None

    priorities = {"ethernet": 0, "wifi": 1, "network": 2}
    return min(interface_kinds, key=lambda kind: priorities.get(kind, 9))


def probe_online_service(
    host: str = DEFAULT_ONLINE_HOST,
    port: int = DEFAULT_ONLINE_PORT,
    *,
    timeout_seconds: float = DEFAULT_ONLINE_PROBE_TIMEOUT_SECONDS,
) -> bool:
    normalized_host = str(host or "").strip()
    if not normalized_host:
        return False

    try:
        normalized_port = int(port)
    except (TypeError, ValueError):
        return False

    if not 1 <= normalized_port <= 65535:
        return False

    try:
        with contextlib.closing(
            socket.create_connection(
                (normalized_host, normalized_port),
                timeout=max(0.1, float(timeout_seconds)),
            )
        ):
            return True
    except OSError:
        return False


def get_online_network_status(
    host: str = DEFAULT_ONLINE_HOST,
    port: int = DEFAULT_ONLINE_PORT,
    *,
    timeout_seconds: float = DEFAULT_ONLINE_PROBE_TIMEOUT_SECONDS,
) -> OnlineNetworkStatus:
    interface_kind = _primary_interface_kind()
    if interface_kind is None:
        return OnlineNetworkStatus(
            transport_kind="offline",
            transport_label=_transport_label("offline"),
            tone="neutral",
            signal_bars=0,
            online_available=False,
            is_connected=False,
            quality_label="Aucun",
        )

    started_at = time.perf_counter()
    is_online_available = probe_online_service(
        host,
        port,
        timeout_seconds=timeout_seconds,
    )
    latency_ms = max(1, int(round((time.perf_counter() - started_at) * 1000)))

    if not is_online_available:
        return OnlineNetworkStatus(
            transport_kind=interface_kind,
            transport_label=_transport_label(interface_kind),
            tone="danger",
            signal_bars=1,
            online_available=False,
            is_connected=True,
            quality_label="Faible",
        )

    if latency_ms <= ONLINE_NETWORK_GOOD_LATENCY_MS:
        return OnlineNetworkStatus(
            transport_kind=interface_kind,
            transport_label=_transport_label(interface_kind),
            tone="success",
            signal_bars=4,
            online_available=True,
            is_connected=True,
            quality_label="Stable",
            latency_ms=latency_ms,
        )

    return OnlineNetworkStatus(
        transport_kind=interface_kind,
        transport_label=_transport_label(interface_kind),
        tone="warning",
        signal_bars=3,
        online_available=True,
        is_connected=True,
        quality_label="Moyen",
        latency_ms=latency_ms,
    )


class OnlineClient:
    def __init__(self):
        self.sock: socket.socket | None = None
        self.running = False
        self.connecting = False
        self.rx_thread: threading.Thread | None = None
        self.events: "queue.Queue[dict]" = queue.Queue()
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._disconnect_requested = False
        self._endpoint: str | None = None
        self.last_input_state: dict[str, bool] | None = None
        self.last_input_send_time = 0.0
        self._last_server_activity_time = 0.0
        self._last_ping_sent_time = 0.0

    @property
    def endpoint(self) -> str | None:
        return self._endpoint

    def connect(self, host: str, port: int, pseudo: str) -> None:
        normalized_host = str(host or "").strip()
        if not normalized_host:
            raise ValueError("Saisis l'adresse du serveur online.")

        try:
            normalized_port = int(port)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Le port du serveur online doit etre un entier valide."
            ) from error

        if not 1 <= normalized_port <= 65535:
            raise ValueError("Le port du serveur online doit rester entre 1 et 65535.")

        normalized_pseudo = str(pseudo or "").strip()
        if not normalized_pseudo:
            raise ValueError("Saisis un pseudo avant de te connecter.")

        with self._lock:
            worker_alive = self.rx_thread is not None and self.rx_thread.is_alive()
            if self.running or self.connecting or worker_alive:
                raise OnlineConnectionError(
                    "Une connexion online est deja active ou en cours."
                )
            self._disconnect_requested = False
            self.connecting = True
            self._endpoint = format_endpoint(normalized_host, normalized_port)
            self.last_input_state = None
            self.last_input_send_time = 0.0
            self._last_server_activity_time = 0.0
            self._last_ping_sent_time = 0.0
            self._clear_events_locked()
            self.rx_thread = threading.Thread(
                target=self._connection_loop,
                args=(normalized_host, normalized_port, normalized_pseudo),
                name="arena-online-rx",
                daemon=True,
            )
            thread = self.rx_thread

        thread.start()

    def send(self, obj: dict) -> None:
        payload = self._pack(obj)

        with self._lock:
            sock = self.sock
            running = self.running
            connecting = self.connecting

        if sock is None or not running:
            if connecting:
                raise OnlineConnectionError(
                    "Connexion online en cours. Reessaie dans un instant."
                )
            raise OnlineConnectionError("Aucune connexion online active.")

        try:
            with self._send_lock:
                sock.sendall(payload)
        except OSError as error:
            raise OnlineConnectionError(_format_runtime_error(error)) from error

    def disconnect(self) -> None:
        with self._lock:
            self._disconnect_requested = True
            self.connecting = False
            self.running = False
            sock = self.sock
            self.sock = None
            self._endpoint = None
            self.last_input_state = None
            self.last_input_send_time = 0.0
            self._last_server_activity_time = 0.0
            self._last_ping_sent_time = 0.0

        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                sock.close()
            except OSError:
                pass

    close = disconnect

    def poll(self) -> dict | None:
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def poll_messages(self) -> list[dict]:
        messages: list[dict] = []
        while True:
            message = self.poll()
            if message is None:
                return messages
            messages.append(message)

    def send_input(
        self,
        up: bool,
        down: bool,
        left: bool,
        right: bool,
    ) -> None:
        state = {
            "up": up,
            "down": down,
            "left": left,
            "right": right,
        }
        now = time.time()

        should_send = (
            state != self.last_input_state or (now - self.last_input_send_time) >= 0.1
        )
        if not should_send:
            return

        try:
            self.send(
                {
                    "type": "INPUT",
                    "up": up,
                    "down": down,
                    "left": left,
                    "right": right,
                }
            )
        except OnlineConnectionError as error:
            message = str(error)
            self.disconnect()
            self.events.put(
                {
                    "type": "DISCONNECTED",
                    "error": message,
                    "message": message,
                }
            )
            return

        self.last_input_state = state
        self.last_input_send_time = now

    def _connection_loop(self, host: str, port: int, pseudo: str) -> None:
        sock: socket.socket | None = None
        disconnect_message: dict | None = None

        try:
            try:
                sock = socket.create_connection(
                    (host, port),
                    timeout=DEFAULT_ONLINE_CONNECT_TIMEOUT_SECONDS,
                )
                sock.settimeout(ONLINE_READ_TIMEOUT_SECONDS)
                self._configure_socket_keepalive(sock)
            except OSError as error:
                disconnect_message = {
                    "type": "DISCONNECTED",
                    "error": _format_connect_error(host, port, error),
                    "message": _format_connect_error(host, port, error),
                }
                return

            with self._lock:
                if self._disconnect_requested:
                    return
                self.sock = sock
                self.running = True
                self.connecting = False
                self._last_server_activity_time = time.monotonic()
                self._last_ping_sent_time = 0.0

            self._send_on_socket(
                sock,
                {"type": "HELLO", "proto": PROTO_VERSION},
            )
            self._send_on_socket(sock, {"type": "LOGIN", "pseudo": pseudo})
            LOGGER.info(
                "Connexion online ouverte vers %s pour %s",
                format_endpoint(host, port),
                pseudo,
            )

            while True:
                with self._lock:
                    if not self.running:
                        break

                message = self._recv_message(sock)
                self.events.put(message)
        except (
            OSError,
            ConnectionError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            OnlineProtocolError,
        ) as error:
            if not self._disconnect_requested:
                disconnect_message = {
                    "type": "DISCONNECTED",
                    "error": _format_runtime_error(error),
                    "message": _format_runtime_error(error),
                }
        finally:
            with self._lock:
                self.running = False
                self.connecting = False
                if self.sock is sock:
                    self.sock = None
                if self.rx_thread is threading.current_thread():
                    self.rx_thread = None
                self._endpoint = None

            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

            if disconnect_message is not None and not self._disconnect_requested:
                self.events.put(disconnect_message)
                LOGGER.warning(
                    "Connexion online interrompue: %s",
                    disconnect_message["error"],
                )

    def _pack(self, obj: dict) -> bytes:
        raw = json.dumps(
            obj,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return struct.pack("!I", len(raw)) + raw

    def _send_on_socket(self, sock: socket.socket, obj: dict) -> None:
        with self._send_lock:
            sock.sendall(self._pack(obj))

    def _configure_socket_keepalive(self, sock: socket.socket) -> None:
        with contextlib.suppress(OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    def _mark_server_activity(self) -> None:
        with self._lock:
            self._last_server_activity_time = time.monotonic()

    def _handle_socket_timeout(self, sock: socket.socket) -> None:
        now = time.monotonic()

        with self._lock:
            if not self.running:
                raise ConnectionAbortedError(
                    "Connexion online fermee avant la fin de la lecture."
                )
            last_server_activity_time = self._last_server_activity_time
            last_ping_sent_time = self._last_ping_sent_time

        if (
            last_server_activity_time
            and (now - last_server_activity_time) >= ONLINE_HEARTBEAT_TIMEOUT_SECONDS
        ):
            raise ConnectionError("Le serveur online ne repond plus.")

        if (now - last_ping_sent_time) < ONLINE_HEARTBEAT_INTERVAL_SECONDS:
            return

        try:
            self._send_on_socket(
                sock,
                {"type": "PING", "ts": time.time()},
            )
        except OSError as error:
            raise ConnectionError(_format_runtime_error(error)) from error

        with self._lock:
            if self.sock is sock:
                self._last_ping_sent_time = now

    def _recv_exact(self, sock: socket.socket, size: int) -> bytes:
        buffer = bytearray()

        while len(buffer) < size:
            with self._lock:
                if not self.running:
                    raise ConnectionAbortedError(
                        "Connexion online fermee avant la fin de la lecture."
                    )

            try:
                chunk = sock.recv(size - len(buffer))
            except socket.timeout:
                self._handle_socket_timeout(sock)
                continue
            except OSError as error:
                raise ConnectionError(_format_runtime_error(error)) from error

            if not chunk:
                raise ConnectionError("Le serveur online a ferme la connexion.")

            self._mark_server_activity()
            buffer.extend(chunk)

        return bytes(buffer)

    def _recv_message(self, sock: socket.socket) -> dict:
        header = self._recv_exact(sock, 4)
        message_size = struct.unpack("!I", header)[0]

        if message_size <= 0 or message_size > MAX_ONLINE_MESSAGE_BYTES:
            raise OnlineProtocolError(
                f"Taille de message online invalide: {message_size}."
            )

        payload = self._recv_exact(sock, message_size)
        message = json.loads(payload.decode("utf-8"))
        if not isinstance(message, dict):
            raise OnlineProtocolError(
                "Le serveur online a renvoye un message non objet."
            )
        return message

    def _clear_events_locked(self) -> None:
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                return
