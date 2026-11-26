"""Bounded remote-only client: untrusted parsing never runs in a DB worker."""

import base64
import json
import logging
from pipeline.parser_errors import ParserUnavailable, ParserRejected

import httpx
from django.conf import settings


def call(operation, data, name="", *, ocr=False, provider=None, force_ocr=False):
    if operation not in {
        "mail", "extract", "extract_native", "detect", "probe", "scan", "scan_configured", "preview",
        "upload_members", "detection_evidence", "dataset_import", "analyze_message",
    }:
        raise ValueError("Unsupported parser operation")
    url = settings.MICE_OCR_PARSER_URL if ocr else settings.MICE_PARSER_URL
    if ocr:
        if provider is None:
            from records.ocr_settings import configuration
            values = configuration()
            if not values["enabled"]:
                raise RuntimeError("OCR disabled")
            provider = values["provider"]
        if provider not in {"rapidocr", "paddleocr", "surya"}:
            raise ValueError("Unknown OCR provider")
        if provider == "surya":
            url = settings.MICE_SURYA_URL
    if not url:
        raise RuntimeError("Isolated parser is not configured; local fallback forbidden")
    limit = 96 * 1024**2 if operation == "analyze_message" else settings.MICE_MAX_MESSAGE_BYTES
    if len(data) > limit:
        raise ValueError("Parser input limit")
    service = "surya" if ocr and provider == "surya" else "ocr-parser" if ocr else "parser"
    try:
        return _request(operation, data, name, ocr, provider, force_ocr, url, service)
    except httpx.TransportError as exc:
        reason = "timeout" if isinstance(exc, httpx.TimeoutException) else "transport"
        error = ParserUnavailable(operation, service, reason)
        logging.getLogger(__name__).warning("%s", error)
        raise error from None


def _request(operation, data, name, ocr, provider, force_ocr, url, service):
    request = json.loads(data) if operation == "analyze_message" else {
        "operation": operation, "data": base64.b64encode(data).decode(), "name": name[:1024],
        **({"provider": provider, "force_ocr": force_ocr} if ocr else {}),
    }
    if not isinstance(request, dict):
        raise ValueError("Invalid parser request")
    if operation == "analyze_message" and len(json.dumps(request).encode()) > 96 * 1024**2:
        raise ValueError("Parser request limit")
    with httpx.Client(
        timeout=settings.MICE_ANALYSIS_WALL_TIMEOUT + 15 if operation == "analyze_message" else 650 if ocr and provider == "surya" else settings.MICE_PARSER_TIMEOUT, trust_env=False, follow_redirects=False
    ) as client:
        with client.stream(
            "POST",
            url.rstrip("/") + ("/analyze" if operation == "analyze_message" else "/parse"),
            json=request,
        ) as response:
            if response.status_code >= 300:
                status = response.status_code
                transient = status in {408, 425, 429, 500, 502, 503, 504}
                reasons = {429: "overloaded", 503: "unavailable", 504: "upstream_timeout",
                           413: "input_limit", 422: "input_rejected", 400: "invalid_request"}
                reason = reasons.get(status, "http_error")
                # Only fixed tokens from our protocol; never echo arbitrary headers/body.
                header = response.headers.get("X-Parser-Reason", "")
                if header in {"busy", "queue_full", "sandbox_timeout", "sandbox_failed", "sandbox_memory_limit", "ocr_unavailable", "input_rejected"}:
                    reason = header
                try:
                    delay = min(300, max(0, int(response.headers.get("Retry-After", "0"))))
                except ValueError:
                    delay = 0
                cls = ParserUnavailable if transient else ParserRejected
                error = cls(operation, service, reason, status, delay)
                logging.getLogger(__name__).warning("%s", error)
                raise error
            payload = bytearray()
            for chunk in response.iter_bytes():
                if len(payload) + len(chunk) > settings.MICE_PARSER_RESPONSE_BYTES:
                    raise ValueError("Parser output limit")
                payload.extend(chunk)
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise ValueError("Invalid parser response")
    if operation == "mail":
        result["attachments"] = [
            [name, mime, base64.b64decode(encoded, validate=True)]
            for name, mime, encoded in result["attachments"]
        ]
    return result
