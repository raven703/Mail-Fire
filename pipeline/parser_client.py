"""Bounded remote-only client: untrusted parsing never runs in a DB worker."""

import base64
import json

import httpx
from django.conf import settings


def call(operation, data, name="", *, ocr=False):
    if operation not in {
        "mail", "extract", "extract_native", "detect", "probe", "scan", "preview",
        "upload_members", "detection_evidence", "dataset_import",
    }:
        raise ValueError("Unsupported parser operation")
    url = settings.MICE_OCR_PARSER_URL if ocr else settings.MICE_PARSER_URL
    if not url:
        raise RuntimeError("Isolated parser is not configured; local fallback forbidden")
    if len(data) > settings.MICE_MAX_MESSAGE_BYTES:
        raise ValueError("Parser input limit")
    with httpx.Client(
        timeout=settings.MICE_PARSER_TIMEOUT, trust_env=False, follow_redirects=False
    ) as client:
        with client.stream(
            "POST",
            url.rstrip("/") + "/parse",
            json={
                "operation": operation,
                "data": base64.b64encode(data).decode(),
                "name": name[:1024],
            },
        ) as response:
            response.raise_for_status()
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
