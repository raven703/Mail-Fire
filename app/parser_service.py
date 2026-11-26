"""Secret-free parser broker. Only bounded mail/extraction operations are exposed."""

import base64
import json
import os
import subprocess
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

def local_call(*args, **kwargs):
    # Keep HTTP admission tests and the coordinator free of parser-only imports.
    from app.sandbox import local_call as sandbox_call
    return sandbox_call(*args, **kwargs)

LIMIT = 70 * 1024**2
UNIFIED = os.environ.get("MICE_UNIFIED_ANALYSIS_ENABLED", "false").lower() == "true"
CONCURRENCY = int(os.environ.get("MICE_PARSER_CONCURRENCY", "2")) if UNIFIED else 1
WAITING = int(os.environ.get("MICE_PARSER_QUEUE_SIZE", "3"))
WAIT = float(os.environ.get("MICE_PARSER_SLOT_WAIT_SECONDS", "5"))
if not 1 <= CONCURRENCY <= 32 or not 0 <= WAITING <= 32 or not 0 <= WAIT <= 30:
    raise ValueError("Invalid parser admission limits")
slots = threading.BoundedSemaphore(CONCURRENCY)
admission = threading.BoundedSemaphore(CONCURRENCY + WAITING)
broker = None

def busy(handler):
    handler.send_response(503)
    handler.send_header("Retry-After", "5")
    handler.send_header("Content-Length", "0")
    handler.end_headers()


class Handler(BaseHTTPRequestHandler):
    def parser_error(self, status, reason):
        payload = json.dumps({"error": reason}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Parser-Reason", reason)
        if status in {429, 503, 504}:
            self.send_header("Retry-After", "5")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(payload)
        logging.getLogger(__name__).warning("parser status=%d reason=%s", status, reason)

    def do_GET(self):
        if self.path.startswith("/health?provider="):
            from importlib.metadata import version
            from app.config import settings
            provider = self.path.partition("=")[2]
            allowed = {"surya"} if settings().ocr_backend == "surya" else {"rapidocr", "paddleocr"}
            if provider not in allowed:
                self.send_error(503)
                return
            import os
            from pathlib import Path
            model = {"surya": "detection-2025_05_07/recognition-2025_05_16",
                     "rapidocr": "cyrillic_PP-OCRv5_rec_mobile", "paddleocr": "ru_PP-OCRv3"}[provider]
            if provider == "surya":
                ready = all(Path(os.environ.get(key, "/missing"), "model.safetensors").is_file()
                            for key in ("DETECTOR_MODEL_CHECKPOINT", "RECOGNITION_MODEL_CHECKPOINT"))
            elif provider == "paddleocr":
                ready = Path(settings().ocr_model_root, "paddle/rec").is_dir()
            else:
                import rapidocr
                ready = Path(rapidocr.__file__).parent.joinpath("models/cyrillic_PP-OCRv5_rec_mobile.onnx").is_file()
            payload = json.dumps({"version": version("surya-ocr" if provider == "surya" else provider),
                                  "model": model, "device": os.environ.get("TORCH_DEVICE", "cpu") if provider == "surya" else "cpu"}).encode()
            self.send_response(200 if ready else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/resources":
            try:
                result = subprocess.run(
                    ["sh", "/run/mice-resource-probe.sh", "print"],
                    capture_output=True, timeout=3, check=True,
                )
            except (OSError, subprocess.SubprocessError):
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(result.stdout)))
            self.end_headers()
            self.wfile.write(result.stdout)
            return
        if self.path == "/health" and UNIFIED and (broker is None or broker.process.poll() is not None):
            self.send_error(503)
            return
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self):
        if self.path not in {"/parse", "/analyze"}:
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if self.path == "/analyze" and not UNIFIED:
            self.send_error(404)
            return
        if not 0 < size <= (96 * 1024**2 if self.path == "/analyze" else LIMIT):
            self.send_error(413)
            return
        if not admission.acquire(blocking=False):
            self.parser_error(429, "queue_full")
            return
        # Short bounded wait absorbs contention without allocating request bodies.
        if not slots.acquire(timeout=WAIT):
            admission.release()
            self.parser_error(503, "busy")
            return
        try:
            self.connection.settimeout(650)
            body = self.rfile.read(size)
            request = json.loads(body)
            if not isinstance(request, dict):
                raise ValueError("Expected request object")
            if self.path == "/analyze":
                if not UNIFIED or broker is None:
                    self.send_error(422, "Unified analysis disabled")
                    return
                from app.analysis_broker import AnalysisRejected, AnalysisUnavailable
                try:
                    if (not isinstance(request.get("original"), str) or not isinstance(request.get("configuration"), dict)
                            or type(request.get("ocr_enabled")) is not bool):
                        raise ValueError("Invalid analysis request")
                    payload = json.dumps(broker.analyze(request), ensure_ascii=False).encode()
                except AnalysisRejected as exc:
                    reason = str(exc)
                    self.parser_error(422, reason if reason in {"sandbox_timeout", "sandbox_memory_limit", "sandbox_failed"} else "input_rejected")
                    return
                except AnalysisUnavailable:
                    self.parser_error(503, "busy")
                    return
                from app.config import settings
                if len(payload) > settings().parser_response_bytes:
                    raise ValueError("Parser response limit")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if size > LIMIT:
                self.send_error(413)
                return
            if request.get("operation") not in {
                "detect",
                "detection_evidence",
                "dataset_import",
                "upload_members",
                "mail",
                "extract",
                "extract_native",
                "probe",
                "scan",
                "scan_configured",
                "preview",
            }:
                raise ValueError("Unsupported operation")
            data = base64.b64decode(request["data"], validate=True)
            provider = request.get("provider")
            if provider is not None:
                from app.config import settings
                allowed = {"surya"} if settings().ocr_backend == "surya" else {"rapidocr", "paddleocr"}
                if provider not in allowed:
                    raise ValueError("Unsupported provider")
            result = local_call(request["operation"], data, request.get("name", "")[:1024],
                                provider=provider, force_ocr=request.get("force_ocr") is True)
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
        except subprocess.TimeoutExpired:
            self.parser_error(504, "sandbox_timeout")
        except (ValueError, KeyError, TypeError):
            self.parser_error(422, "input_rejected")
        except (RuntimeError, OSError):
            self.parser_error(503, "sandbox_failed")
        except Exception:
            self.parser_error(500, "internal_error")
        finally:
            slots.release()
            admission.release()

    def log_message(self, *args):
        pass  # Do not log filenames, message bodies or raw request content.


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    request_queue_size = 8


if __name__ == "__main__":
    if UNIFIED:
        from app.analysis_broker import AnalysisBroker
        import atexit
        broker = AnalysisBroker()
        atexit.register(broker.close)
    Server(("0.0.0.0", 8090), Handler).serve_forever()
