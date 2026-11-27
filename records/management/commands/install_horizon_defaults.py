"""Explicit opt-in import: never creates categories or enables the detector."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.horizon import validate
from records.models import Category, CategoryRule


class Command(BaseCommand):
    help = "Install disabled PR38 Horizon rules into the 12 EXISTING RU2 categories; no overwrite"

    @transaction.atomic
    def handle(self, *args, **options):
        defaults = json.loads((Path(__file__).resolve().parents[3] / "app/horizon_defaults.json").read_text())
        missing = set(defaults) - set(
            Category.objects.filter(pk__in=defaults)
            .exclude(mode__in=["builtin", "label"])
            .values_list("pk", flat=True)
        )
        if missing:
            raise CommandError(
                "Missing user categories (import existing RU rules first): " + ", ".join(sorted(missing))
            )
        created = 0
        for cid, config in defaults.items():
            _, added = CategoryRule.all_objects.get_or_create(
                pk="horizon-" + cid.removeprefix("pack-ru2-"),
                defaults={
                    "category_id": cid,
                    "kind": "horizon",
                    "enabled": False,
                    "risk": 50,
                    "title": "Horizon Zero-shot (PR38, calibration required)",
                    "config": validate(config),
                },
            )
            created += added
        self.stdout.write(f"{created} disabled rules installed; no categories/settings changed")
