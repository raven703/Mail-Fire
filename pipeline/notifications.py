"""Notification I/O outside transactions; fenced durable completion afterwards."""

import json
import socket
from urllib.parse import urlsplit

import httpx
from django.db import transaction

from pipeline.services import finish, locked_current
from records.models import Outbox


def cef(payload):
    def escape(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("=", "\\=")

    return f"CEF:0|MailFire|AI-DLP|1|dlp|DLP policy finding|{min(10, payload['risk'] // 10)}|externalId={escape(payload['incident_id'])} msg={escape(','.join(payload['categories']))}"


def deliver(job):
    row = Outbox.objects.get(pk=job.payload["outbox_id"])
    if row.status != "SENT":
        parsed = urlsplit(row.destination)
        if parsed.scheme in {"http", "https"}:
            with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
                client.post(
                    row.destination, json=row.payload, headers={"Idempotency-Key": row.payload["incident_id"]}
                ).raise_for_status()
        elif parsed.scheme in {"syslog", "cef"}:
            body = cef(row.payload) if parsed.scheme == "cef" else json.dumps(row.payload, ensure_ascii=False)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(5)
                sock.sendto(("<134>" + body).encode()[:60000], (parsed.hostname, parsed.port or 514))
        else:
            raise ValueError("Unsupported destination scheme")
    with transaction.atomic():
        locked_current(job.pk, job.token)
        row = Outbox.objects.select_for_update().get(pk=row.pk)
        row.status, row.error, row.attempts = "SENT", None, job.attempts
        row.save(update_fields=["status", "error", "attempts"])
        finish(job.pk, job.token, {"delivered": True})
