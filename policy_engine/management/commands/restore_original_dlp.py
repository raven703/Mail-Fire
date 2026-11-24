import json

from django.core.management.base import BaseCommand, CommandError

from policy_engine.restoration import compare, load_configuration, restore


class Command(BaseCommand):
    help = "Restore original DLP catalog, RU2 rules, policies and detector settings; no mail/user/model import."

    def add_arguments(self, parser):
        parser.add_argument("--snapshot")
        parser.add_argument("--rulepack")
        parser.add_argument("--check", action="store_true", help="Read-only comparison; fail on differences")

    def handle(self, *args, **options):
        try:
            expected = load_configuration(options["snapshot"], options["rulepack"])
            report = compare(expected) if options["check"] else restore(expected)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if report["differences"]:
            raise CommandError("Stored DLP configuration differs from source")