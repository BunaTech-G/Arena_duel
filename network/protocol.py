import json
import struct


def encode_message(message: dict) -> bytes:
    """Encode message as [4-byte length][JSON payload]"""
    json_bytes = json.dumps(
        message,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    length_bytes = struct.pack("!I", len(json_bytes))
    return length_bytes + json_bytes


def decode_message(raw_line: bytes) -> dict | None:
    """Decode JSON from raw bytes (legacy format with \n for backward compat)"""
    if not raw_line:
        return None
    line = raw_line.decode("utf-8").strip()
    if not line:
        return None
    return json.loads(line)


def send_message_binary(wfile, message: dict) -> None:
    wfile.write(encode_message(message))
    wfile.flush()


def receive_message_binary(rfile) -> dict | None:
    """Read exact message size from 4-byte prefix then JSON payload"""
    header = rfile.read(4)
    if not header or len(header) < 4:
        return None

    try:
        message_size = struct.unpack("!I", header)[0]
    except struct.error:
        return None

    if message_size <= 0 or message_size > 1024 * 1024:
        return None

    payload = rfile.read(message_size)
    if not payload or len(payload) != message_size:
        return None

    try:
        return json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
