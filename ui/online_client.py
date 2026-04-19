import socket
import json
import struct
import threading
import queue

PROTO_VERSION = 1

class OnlineClient:
    def __init__(self):
        self.sock = None
        self.running = False
        self.rx_thread = None
        self.events = queue.Queue()
        self._lock = threading.Lock()

    def _pack(self, obj: dict) -> bytes:
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return struct.pack("!I", len(raw)) + raw

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Connexion fermée")
            buf += chunk
        return buf

    def _recv_msg(self) -> dict:
        hdr = self._recv_exact(4)
        size = struct.unpack("!I", hdr)[0]
        raw = self._recv_exact(size)
        return json.loads(raw.decode("utf-8"))

    def connect(self, host: str, port: int, pseudo: str):
        with self._lock:
            if self.running:
                return
            self.sock = socket.create_connection((host, port), timeout=5)
            self.sock.settimeout(None)
            self.running = True

        # handshake + login
        self.send({"type": "HELLO", "proto": PROTO_VERSION})
        self.send({"type": "LOGIN", "pseudo": pseudo})

        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()

    def send(self, obj: dict):
        with self._lock:
            if not self.running or not self.sock:
                return
            self.sock.sendall(self._pack(obj))

    def _rx_loop(self):
        try:
            while self.running:
                msg = self._recv_msg()
                self.events.put(msg)
        except Exception as e:
            self.events.put({"type": "DISCONNECTED", "error": str(e)})
        finally:
            with self._lock:
                self.running = False
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def disconnect(self):
        with self._lock:
            self.running = False
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass
            self.sock = None

    def poll(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None