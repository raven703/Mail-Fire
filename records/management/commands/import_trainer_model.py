"""Explicit trusted local import; never activates models or changes existing rows."""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from records.trainer_import import import_models


class Command(BaseCommand):
    help = "Validate a trusted Trainer export on CPU; import inactive only with --commit"

    def add_arguments(self, parser):
        parser.add_argument("folder", type=Path)
        parser.add_argument("--trust-local-artifact", action="store_true", required=True)
        parser.add_argument("--commit", action="store_true")
        parser.add_argument("--name", default="MICE Trainer import")
        parser.add_argument("--model", action="append", dest="selected")

    def handle(self, *args, **options):
        try:
            imported = import_models(options["folder"].expanduser().resolve(), options.get("selected"),
                trusted=options.get("trust_local_artifact", False), commit=options["commit"], name=options["name"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Validated on CPU; imported {len(imported)} inactive models; activation remains manual")
