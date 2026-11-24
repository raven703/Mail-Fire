import logging
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from mice.celery import app
from pipeline.publisher import declare_topology, publish_one
from pipeline.services import recover

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Publish committed dispatch intents with confirms; no domain work execution."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            try:
                close_old_connections()
                # Broker-independent recovery is necessary if Beat cannot deliver.
                recover()
                with app.connection_for_write() as connection:
                    connection.ensure_connection(max_retries=1)
                    declare_topology(connection)
                    while publish_one(connection):
                        pass
            except Exception:
                logger.exception("Outbox publisher failed; committed intents retained")
                if options["once"]:
                    raise
            if options["once"]:
                return
            time.sleep(1)
