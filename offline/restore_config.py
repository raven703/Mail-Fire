import json
import os
import secrets

from django.core import serializers
from django.db import transaction
from identity.models import User
from records.models import CategoryRule, Policy

with transaction.atomic():
    CategoryRule.all_objects.all().delete()
    Policy.objects.all().delete()
    for obj in serializers.deserialize("json", open("/bundle/config.json").read()):
        obj.save()
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", os.environ["ADMIN_PASSWORD"], originals=True)