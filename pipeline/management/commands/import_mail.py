import signal
import threading

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from pipeline.directory import scan


class Command(BaseCommand):
    help = "Import stable EML/MSG files read-only; never move/delete source files."

    def add_arguments(self, parser):
        parser.add_argument("root")
        parser.add_argument("--namespace", required=True)
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--no-recursive", action="store_true")
        parser.add_argument("--stability-seconds", type=float, default=5)
        parser.add_argument("--interval", type=float, default=5)

    def handle(self, *args, **options):
        if options["stability_seconds"] < 0 or options["interval"] <= 0:
            raise CommandError("Invalid scan intervals")
        observed, stop = {}, threading.Event()
        previous = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)}

        def run_scan():
            close_old_connections()
            return scan(
                options["root"], observed, namespace=options["namespace"],
                recursive=not options["no_recursive"], stability_seconds=options["stability_seconds"],
            )

        try:
            while not stop.is_set():
                try:
                    result = run_scan()
                    if not options["watch"]:
                        if stop.wait(options["stability_seconds"]):
                            return
                        result = run_scan()
                    self.stdout.write(str(result))
                    if not options["watch"]:
                        if result["failed"] or result["waiting"]:
                            raise CommandError("Some files failed or are not stable; rerun import")
                        return
                except (OSError, ValueError, DatabaseError) as exc:
                    if not options["watch"]:
                        raise CommandError(type(exc).__name__) from exc
                    self.stderr.write("Import retry: " + type(exc).__name__)
                stop.wait(options["interval"])
        finally:
            close_old_connections()
            for sig, handler in previous.items():
                signal.signal(sig, handler)