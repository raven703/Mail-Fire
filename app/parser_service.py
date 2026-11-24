"""Secret-free parser broker. Only bounded mail/extraction operations are exposed."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from app.sandbox import local_call

LIMIT = 70 * 1024**2
slots = threading.BoundedSemaphore(1)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/parse":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if not 0 < size <= LIMIT:
            self.send_error(413)
            return
        if not slots.acquire(blocking=False):
            self.send_error(503)
            return
        try:
            self.connection.settimeout(130)
            body = self.rfile.read(size)
            request = json.loads(body)
            if request.get("operation") not in {
                "detect",
                "mail",
                "extract",
                "extract_native",
                "probe",
                "scan",
                "preview",
            }:
                raise ValueError("Unsupported operation")
            data = base64.b64decode(request["data"], validate=True)
            result = local_call(request["operation"], data, request.get("name", "")[:1024])
            if request["operation"] == "mail":
                result["attachments"] = [
                    [n, m, base64.b64encode(d).decode()] for n, m, d in result["attachments"]
                ]
            payload = json.dumps(result).encode()
            from app.config import settings

            if len(payload) > settings().parser_response_bytes:
                raise ValueError("Parser response limit")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception:
            self.send_error(422, "Parser rejected input")
        finally:
            slots.release()

    def log_message(self, *args):
        pass  # Do not log filenames, message bodies or raw request content.


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 8


if __name__ == "__main__":
    Server(("0.0.0.0", 8090), Handler).serve_forever()
