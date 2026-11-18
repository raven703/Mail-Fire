import asyncio
import ipaddress
import uuid

from aiosmtpd.controller import Controller

from app.config import settings
from app.db import transaction
from app.mail import ingest


class Collector:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not any(
            ipaddress.ip_address(session.peer[0]) in ipaddress.ip_network(n.strip())
            for n in settings().smtp_networks.split(",")
        ):
            return "550 Source not allowed"
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        try:

            def save():
                with transaction() as db:
                    # No reliable upstream delivery ID: independent receipts remain
                    # separate events. Bytes are deduplicated, events are not guessed.
                    ingest(
                        db,
                        envelope.original_content,
                        "smtp",
                        "smtp:" + uuid.uuid4().hex,
                        "BCC",
                        {
                            "peer": session.peer[0],
                            "mail_from": envelope.mail_from,
                            "rcpt_tos": envelope.rcpt_tos,
                        },
                    )

            await asyncio.to_thread(save)
            return "250 Stored"
        except Exception:
            return "451 Storage unavailable"


def main():
    controller = Controller(
        Collector(),
        hostname=settings().smtp_host,
        port=settings().smtp_port,
        data_size_limit=settings().max_message_bytes,
        decode_data=False,
    )
    controller.start()
    import threading

    threading.Event().wait()


if __name__ == "__main__":
    main()
