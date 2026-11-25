import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identity.models import User
from records.models import Setting


class Command(BaseCommand):
    help = "Create administrator without resetting existing credentials."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        from app.text_normalizer import DEFAULTS

        for key, value in {
            "normalizer": DEFAULTS,
            "detectors": {},
            "integrations": {"destinations": []},
        }.items():
            Setting.objects.get_or_create(pk=key, defaults={"value": value})
        # Initialize only a genuinely empty custom catalog. Existing deployments
        # require the explicit backed-up upgrade command, never an implicit reset.
        from records.models import CategoryRule, Policy
        if not CategoryRule.all_objects.exists() and not Policy.objects.exists() and not Setting.objects.filter(pk="dlp_rulepack").exists():
            from policy_engine.ru3 import upgrade
            upgrade(backup_dir=os.environ.get("MICE_DLP_BACKUP_DIR", "/state/dlp-backups"), apply=True)
        if User.objects.filter(username=username).exists():
            self.stdout.write("Administrator already exists; credentials unchanged")
            return
        password = os.environ.get("ADMIN_PASSWORD", "")
        if len(password) < 16:
            raise CommandError("ADMIN_PASSWORD must contain at least 16 characters")
        User.objects.create_superuser(username, password, originals=True)
        self.stdout.write(self.style.SUCCESS("MICE administrator created"))