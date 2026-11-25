"""Trusted IPC/OCR broker; no network permissions added to sandbox."""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import threading
import shutil
import asyncio

import httpx

from app.analysis_ipc import receive, send
from app.config import settings


class AnalysisUnavailable(RuntimeError):
    pass


class AnalysisBroker:
    def __init__(self):
        from app.analysis_launcher import nondumpable
        nondumpable()
        self.directory = tempfile.TemporaryDirectory(prefix="mice-launcher-")
        self.path = os.path.join(self.directory.name, "control.sock")
        self.timeout = int(os.environ.get("MICE_ANALYSIS_WALL_TIMEOUT", "600"))
        self.ocr_url = "http://ocr-parser:8090/parse"
        self.lock = threading.Lock()
        self.closed = False
        self._start()
        self.stopped = threading.Event()
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.monitor.start()

    def _monitor(self):
        while not self.stopped.wait(.2):
            with self.lock:
                if self.process.poll() is not None:
                    self._clean_orphans()

    def _clean_orphans(self):
        for entry in os.scandir(self.directory.name):
            if entry.name.startswith(('mice-mail-', 'mice-isolation-check-')) and entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path, ignore_errors=True)

    def _start(self):
        # Called only initially or after the previous launcher has been waited.
        self._clean_orphans()
        if os.path.exists(self.path):
            os.unlink(self.path)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(self.path)
            listener.listen(32)
            env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
            env['TMPDIR'] = self.directory.name
            self.process = subprocess.Popen(
                [sys.executable, "-m", "app.analysis_launcher", str(listener.fileno())],
                pass_fds=(listener.fileno(),), env=env,
            )
            listener.settimeout(30)
            try:
                with listener.accept()[0] as ready:
                    ready.settimeout(30)
                    if receive(ready) != {'type': 'ready'}:
                        raise RuntimeError('Invalid launcher readiness')
                    send(ready, {'type': 'accepted'})
            except BaseException:
                self.process.kill()
                self.process.wait()
                raise AnalysisUnavailable('Analysis launcher startup failed') from None

    def close(self):
        self.closed = True
        self.stopped.set()
        self.monitor.join(timeout=2)
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.directory.cleanup()

    def ocr(self, frame, timeout, provider="rapidocr"):
        if provider not in {"rapidocr", "paddleocr", "surya"}:
            raise ValueError("Unsupported OCR provider")
        data = base64.b64decode(frame["data"], validate=True)
        if len(data) > settings().max_message_bytes:
            raise ValueError("OCR input limit")
        name = frame["name"]
        if not isinstance(name, str) or len(name) > 1024:
            raise ValueError("OCR filename limit")
        try:
            async def fetch():
                async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
                    url = "http://ocr-surya:8090/parse" if provider == "surya" else self.ocr_url
                    async with client.stream("POST", url, json={
                        "operation": "extract", "data": frame["data"], "name": name, "provider": provider,
                    }) as response:
                        response.raise_for_status()
                        payload = bytearray()
                        async for chunk in response.aiter_bytes():
                            payload.extend(chunk)
                            if len(payload) > settings().parser_response_bytes:
                                raise ValueError("OCR response limit")
                        return payload

            async def bounded():
                return await asyncio.wait_for(fetch(), timeout=timeout)

            result = json.loads(asyncio.run(bounded()))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                raise AnalysisUnavailable("OCR temporarily unavailable") from None
            return {"text": "", "status": "FAILED", "details": {"error": "OCRRejected"}}
        except (httpx.TransportError, TimeoutError):
            raise AnalysisUnavailable("OCR transport unavailable") from None
        if (not isinstance(result.get("text"), str) or not isinstance(result.get("details"), dict)
                or result.get("status") not in {"ANALYZED", "PARTIAL", "FAILED", "ENCRYPTED", "UNSUPPORTED"}):
            raise ValueError("Invalid OCR response")
        return result

    def analyze(self, request):
        with self.lock:
            if self.closed:
                raise AnalysisUnavailable("Analysis broker closed")
            if self.process.poll() is not None:
                self.process.wait()
                self._start()
                raise AnalysisUnavailable("Analysis launcher restarted; retry request")
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
                    if frame.get('type') == 'helper':
                        count += 1
                        if count > settings().max_objects * 10:
                            raise ValueError('Helper request count limit')
                        operation = frame.get('operation')
                        data = base64.b64decode(frame['data'], validate=True)
                        if len(data) > settings().max_message_bytes:
                            raise ValueError('Helper input limit')
                        if operation not in {'regex', 'gitleaks'}:
                            raise ValueError('Unsupported helper operation')
                        try:
                            if operation == 'regex':
                                from app.sandbox import local_call
                                name = frame.get('name', '')
                                if not isinstance(name, str) or len(name) > 16384:
                                    raise ValueError('Regex pattern limit')
                                result = local_call('regex', data, name, isolated=True, timeout=remaining)
                            else:
                                # Separate restricted sandbox, not the trusted broker.
                                from app.sandbox import local_call
                                result = local_call('gitleaks', data, isolated=True, timeout=remaining)
                            send(connection, {'type': 'helper_result', 'result': result})
                        except subprocess.TimeoutExpired:
                            send(connection, {'type': 'helper_result', 'timeout': True})
                        continue
                    if frame.get("type") != "ocr" or not request["ocr_enabled"]:
                        raise ValueError("Invalid sandbox request")
                    count += 1
                    if count > settings().max_objects:
                        raise ValueError("OCR request count limit")
                    result = self.ocr(frame, min(130, remaining), request.get("ocr_provider", "rapidocr"))
                    send(connection, {"type": "ocr_result", "result": result})
            except (OSError, EOFError):
                raise AnalysisUnavailable("Analysis launcher unavailable") from None
