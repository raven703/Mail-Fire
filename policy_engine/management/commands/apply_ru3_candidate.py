import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from policy_engine.restoration import load_configuration
from policy_engine.catalog_service import revision
from policy_engine.rule_config import validate_config
from records.models import CategoryRule, Policy

class Command(BaseCommand):
    help = "Preview or apply RU3 candidate to restored RU2 catalog; preserve policy state and historical snapshots."
    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        old = load_configuration()
        path = settings.BASE_DIR / "config/rulepacks/ru3_candidate.json"
        new = load_configuration(rulepack=path)
        pack = json.loads(Path(path).read_text())
        changes = []
        prior = {r["id"]: r for r in old["rules"]}
        for spec in new["rules"]:
            row = CategoryRule.objects.select_for_update().filter(pk=spec["id"]).first()
            before = prior.get(spec["id"])
            fields = {k: v for k, v in spec.items() if k != "id"}
            if row and all(getattr(row, k) == v for k, v in fields.items()):
                continue
            if before and (row is None or any(getattr(row, k) != v for k, v in before.items() if k != "id")):
                raise CommandError("RU2 rule changed locally: " + spec["id"])
            if row and not before:
                raise CommandError("New rule ID already occupied: " + spec["id"])
            changes.append("rule " + spec["title"])
            if options["apply"]:
                CategoryRule.objects.update_or_create(pk=spec["id"], defaults=fields)
        target = {p["name"]: p for p in pack["policies"]}
        for spec in old["policies"]:
            row = Policy.objects.select_for_update().filter(pk=spec["id"]).first()
            if row is None:
                raise CommandError("Missing policy: " + spec["id"])
            candidate = {k: target[spec["name"]][k] for k in spec["conditions"]}
            if row.conditions == candidate:
                continue
            if row.conditions != spec["conditions"]:
                raise CommandError("Policy changed locally: " + spec["id"])
            changes.append("policy " + row.name)
            if options["apply"]:
                revision(row)
                row.conditions = candidate
                row.version += 1
                row.save(update_fields=["conditions", "version"])
                revision(row)
        self.stdout.write(json.dumps({"applied": options["apply"], "changes": changes}, ensure_ascii=False, indent=2))
