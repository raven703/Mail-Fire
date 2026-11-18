import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.integrations import send

PAYLOAD = {
    "incident_id": "synthetic-incident",
    "risk": 80,
    "categories": ["SECRET"],
    "event_id": "synthetic-event",
}


def test_real_http_siem_delivery():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(
                (
                    self.headers.get("Idempotency-Key"),
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                )
            )
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        send(f"http://127.0.0.1:{server.server_port}/siem", PAYLOAD)
        assert received == [("synthetic-incident", PAYLOAD)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_udp_cef():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        send(f"cef://127.0.0.1:{receiver.getsockname()[1]}", PAYLOAD)
        data, _ = receiver.recvfrom(65535)
        assert b"CEF:0|MailFire" in data
        assert b"synthetic-incident" in data
