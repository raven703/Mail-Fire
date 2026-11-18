"""Clamd INSTREAM client. Service failure is never reported as clean."""

import io

from app.config import settings


def scan(data, name):
    if not settings().clamav_host:
        return {"status": "DISABLED", "findings": []}
    import clamd

    from app.advanced_detectors import finding

    client = clamd.ClamdNetworkSocket(host=settings().clamav_host, port=settings().clamav_port, timeout=30)
    result = client.instream(io.BytesIO(data))
    status, signature = result["stream"]
    if status not in {"OK", "FOUND"}:
        raise RuntimeError("ClamAV rejected stream")
    return {
        "status": status,
        "findings": [
            finding(
                "MALWARE", "clamav", risk=100, reason="Антивирусная сигнатура: " + signature, filename=name
            )
        ]
        if status == "FOUND"
        else [],
    }
