"""Clamd INSTREAM client. Service failure is never reported as clean."""

import io


def scan(data, name, *, config=None):
    if config is None:
        from app.config import settings

        config = settings()
    if not config.clamav_host:
        return {"status": "DISABLED", "findings": []}
    import clamd

    from app.advanced_detectors import finding

    client = clamd.ClamdNetworkSocket(host=config.clamav_host, port=config.clamav_port, timeout=30)
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
