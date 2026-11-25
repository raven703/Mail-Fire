"""Trusted IPC/OCR broker; no network permissions added to sandbox."""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from app.analysis_ipc import receive, send
from app.config import settings


class AnalysisUnavailable(RuntimeError):
    pass


class AnalysisBroker:
    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="mice-launcher-")
        self.path = os.path.join(self.directory.name, "control.sock")
        self.timeout = int(os.environ.get("MICE_ANALYSIS_WALL_TIMEOUT", "600"))
        self.ocr_url = "http://ocr-parser:8090/parse"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(self.path)
            listener.listen(32)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
            self.process = subprocess.Popen(
                [sys.executable, "-m", "app.analysis_launcher", str(listener.fileno())],
                pass_fds=(listener.fileno(),), env=env,
            )

    def ocr(self, frame, timeout):
        data = base64.b64decode(frame["data"], validate=True)
        if len(data) > settings().max_message_bytes:
            raise ValueError("OCR input limit")
        name = frame["name"]
        if not isinstance(name, str) or len(name) > 1024:
            raise ValueError("OCR filename limit")
        try:
            with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
                with client.stream("POST", self.ocr_url, json={
                    "operation": "extract", "data": frame["data"], "name": name,
                }) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > settings().parser_response_bytes:
                            raise ValueError("OCR response limit")
            result = json.loads(payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {429, 502, 503, 504}:
                raise AnalysisUnavailable("OCR temporarily unavailable") from None
            return {"text": "", "status": "FAILED", "details": {"error": "OCRRejected"}}
        except httpx.TransportError:
            raise AnalysisUnavailable("OCR transport unavailable") from None
        if (not isinstance(result.get("text"), str) or not isinstance(result.get("details"), dict)
                or result.get("status") not in {"ANALYZED", "PARTIAL", "FAILED", "ENCRYPTED", "UNSUPPORTED"}):
            raise ValueError("Invalid OCR response")
        return result

    def analyze(self, request):
        if self.process.poll() is not None:
            raise AnalysisUnavailable("Analysis launcher stopped")
        deadline = time.monotonic() + self.timeout
        count = 0
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.timeout)
            try:
                connection.connect(self.path)
                send(connection, request)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AnalysisUnavailable("Analysis deadline exceeded")
                    connection.settimeout(remaining)
                    frame = receive(connection)
                    if frame.get("type") == "result":
                        return frame["result"]
                    if frame.get("type") == "error":
                        raise ValueError("Analysis sandbox rejected input")
                    if frame.get("type") != "ocr" or not request["ocr_enabled"]:
                        raise ValueError("Invalid sandbox request")
                    count += 1
                    if count > settings().max_objects:
                        raise ValueError("OCR request count limit")
                    result = self.ocr(frame, min(130, remaining))
                    send(connection, {"type": "ocr_result", "result": result})
            except (OSError, EOFError):
                raise AnalysisUnavailable("Analysis launcher unavailable") from None
