import json


def encode_message(message: dict) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(raw_line: bytes) -> dict | None:
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
    line = rfile.readline()
    if not line:
        return None
    return decode_message(line)
