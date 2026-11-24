"""BCC collector: acknowledge DATA only after durable PostgreSQL acceptance."""

import asyncio
import ipaddress
from uuid import uuid4

from django.conf import settings
from django.db import close_old_connections

from pipeline.ingestion import accept


class Collector:
    def __init__(self, networks=None):
        self.networks = tuple(
            ipaddress.ip_network(value.strip())
            for value in (settings.MICE_SMTP_NETWORKS if networks is None else networks).split(",")
            if value.strip()
        )

    def allowed(self, session):
        try:
            address = ipaddress.ip_address(session.peer[0])
            return any(address in network for network in self.networks)
        except (ValueError, TypeError, IndexError):
            return False

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not self.allowed(session):
            return "550 Source not allowed"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        if not self.allowed(session):
            return "550 Source not allowed"
        data = envelope.original_content
        if not data or len(data) > settings.MICE_MAX_MESSAGE_BYTES:
            return "552 Invalid message size"

        def save():
            close_old_connections()
            try:
                # SMTP has no reliable upstream delivery key: do not guess it
                # from Message-ID or bytes. Independent receipts are events.
                accept(
                    data, "smtp", "smtp:" + uuid4().hex, "BCC",
                    {"peer": session.peer[0], "mail_from": envelope.mail_from,
                     "rcpt_tos": list(envelope.rcpt_tos)},
                )
            finally:
                close_old_connections()

        try:
            await asyncio.to_thread(save)
        except Exception:
            return "451 Storage unavailable"
        return "250 Stored"