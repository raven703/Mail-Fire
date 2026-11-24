import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from pipeline.smtp import Collector


class Command(BaseCommand):
    help = "Collect allowlisted SMTP BCC mail with durable acceptance (not an SMTP relay)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=2525)

    def handle(self, *args, **options):
        from aiosmtpd.controller import Controller

        try:
            collector = Collector()
        except ValueError as exc:
            raise CommandError("Invalid MICE_SMTP_NETWORKS") from exc
        stop = threading.Event()
        previous = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
        controller = Controller(
            collector, hostname=options["host"], port=options["port"],
            data_size_limit=settings.MICE_MAX_MESSAGE_BYTES, decode_data=False,
        )
        try:
            controller.start()
            self.stdout.write("SMTP collector ready")
            stop.wait()
        finally:
            controller.stop()
            for sig, handler in previous.items():
                signal.signal(sig, handler)