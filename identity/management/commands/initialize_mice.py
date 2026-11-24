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
        if User.objects.filter(username=username).exists():
            self.stdout.write("Administrator already exists; credentials unchanged")
            return
        password = os.environ.get("ADMIN_PASSWORD", "")
        if len(password) < 16:
            raise CommandError("ADMIN_PASSWORD must contain at least 16 characters")
        User.objects.create_superuser(username, password, originals=True)
        self.stdout.write(self.style.SUCCESS("MICE administrator created"))