"""Bounded private IPC; a child inherits a connected socket, never a network API."""
import base64
import json
import struct

MAX_FRAME = 128 * 1024**2


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(min(size - len(data), 65536))
        if not chunk:
            raise EOFError("Analysis IPC closed")
        data.extend(chunk)
    return bytes(data)


def receive(sock):
    size = struct.unpack("!I", read_exact(sock, 4))[0]
    if not 0 < size <= MAX_FRAME:
        raise ValueError("Analysis IPC frame limit")
    value = json.loads(read_exact(sock, size))
    if not isinstance(value, dict):
        raise ValueError("Invalid analysis IPC frame")
    return value


def send(sock, value):
    encoded = json.dumps(value, ensure_ascii=False).encode()
    if not 0 < len(encoded) <= MAX_FRAME:
        raise ValueError("Analysis IPC frame limit")
    sock.sendall(struct.pack("!I", len(encoded)))
    sock.sendall(encoded)


def request_ocr(sock, data, name):
    send(sock, {"type": "ocr", "data": base64.b64encode(data).decode(), "name": name[:1024]})
    answer = receive(sock)
    if answer.get("type") != "ocr_result":
        raise RuntimeError("Invalid OCR gateway response")
    return answer["result"]
