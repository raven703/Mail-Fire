"""Transactional SIEM outbox. Destinations are administrator-controlled only."""

import json
import socket
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.db import transaction
from app.models import Diagnostic, Outbox, Setting, now


def enqueue(session, incident):
    config = session.get(Setting, "integrations")
    if not config:
        return
    for destination in config.value.get("destinations", []):
        if not destination.get("enabled", True):
            continue
        target = destination["url"]
        if session.scalar(
            select(Outbox.id).where(Outbox.incident_id == incident.id, Outbox.destination == target)
        ):
            continue
        payload = {
            "class_uid": 2001,
            "category_uid": 2,
            "activity_id": 1,
            "time": now().isoformat(),
            "event_id": incident.event_id,
            "incident_id": incident.id,
            "risk": incident.risk,
            "categories": sorted({f["category"] for f in incident.findings}),
            "url": "/incidents/" + incident.id,
        }
        session.add(Outbox(incident_id=incident.id, destination=target, payload=payload))


def cef(payload):
    def escape(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("=", "\\=")

    return f"CEF:0|MailFire|AI-DLP|1|dlp|DLP policy finding|{min(10, payload['risk'] // 10)}|externalId={escape(payload['incident_id'])} msg={escape(','.join(payload['categories']))}"


def send(destination, payload):
    parsed = urlsplit(destination)
    if parsed.scheme in {"http", "https"}:
        # Redirects disabled: avoid unreviewed destination changes. Explicit
        # internal endpoints are allowed because corporate SIEMs may be internal.
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                destination, json=payload, headers={"Idempotency-Key": payload["incident_id"]}
            )
            response.raise_for_status()
    elif parsed.scheme in {"syslog", "cef"}:
        body = cef(payload) if parsed.scheme == "cef" else json.dumps(payload, ensure_ascii=False)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.sendto(("<134>" + body).encode()[:60000], (parsed.hostname, parsed.port or 514))
    else:
        raise ValueError("Unsupported destination scheme")


def deliver_one():
    # Short bounded network call while holding one outbox row; other workers
    # skip it. Crash before commit may resend: receiver must honor idempotency.
    with transaction() as session:
        row = session.scalar(
            select(Outbox)
            .where(Outbox.status == "PENDING", Outbox.available_at <= now())
            .order_by(Outbox.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not row:
            return False
        row.attempts += 1
        try:
            send(row.destination, row.payload)
            row.status, row.error = "SENT", None
        except Exception as exc:
            row.error = type(exc).__name__
            row.status = "DEAD" if row.attempts >= 8 else "PENDING"
            row.available_at = now() + timedelta(seconds=min(3600, 2**row.attempts))
            session.add(
                Diagnostic(
                    service="outbox",
                    level="ERROR",
                    event="delivery_failed",
                    details={"outbox_id": row.id, "exception": type(exc).__name__},
                )
            )
        return True
