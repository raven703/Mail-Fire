import json
from django.core.management.base import BaseCommand, CommandError
from policy_engine.ru3_pii import apply_pii


class Command(BaseCommand):
    help = "Preview or apply the targeted RU3 PII rule calibration."
    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup-dir")

    def handle(self, *args, **options):
        try:
            result = apply_pii(apply=options["apply"], backup_dir=options["backup_dir"])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
