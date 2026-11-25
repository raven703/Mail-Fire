import json

from django.core.management.base import BaseCommand, CommandError

from policy_engine.ru3 import upgrade


class Command(BaseCommand):
    help = "Preview or atomically install RU3; --apply requires a durable backup directory."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup-dir")

    def handle(self, *args, **options):
        if options["apply"] and not options["backup_dir"]:
            raise CommandError("--backup-dir is required for application")
        try:
            result = upgrade(backup_dir=options["backup_dir"], apply=options["apply"])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))