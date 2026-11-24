from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identity.models import User
from records.models import Account


class Command(BaseCommand):
    help = "Copy accounts to Django Auth, retaining IDs; never overwrite existing users."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for account in Account.objects.select_for_update().order_by("id"):
            if account.role not in {"admin", "analyst", "observer"}:
                raise CommandError(f"Unknown role for account {account.pk}")
            if User.objects.filter(pk=account.pk).exists():
                continue
            if User.objects.filter(username=account.username).exists():
                raise CommandError(f"Username collision for account {account.pk}")
            if not account.password_hash.startswith("$argon2id$"):
                raise CommandError(f"Unsupported password hash for account {account.pk}")
            User.objects.create(
                id=account.pk,
                username=account.username,
                password="legacy_argon2$" + account.password_hash,
                role=account.role,
                originals=account.originals,
                is_active=account.enabled,
                is_staff=account.role == "admin",
                date_joined=account.created_at,
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {created} accounts; legacy sessions not imported"))
