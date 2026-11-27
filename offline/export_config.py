"""Run with Django initialized, inside a READ ONLY database transaction."""
import json
import re

from django.core import serializers
from django.db import connection, transaction
from records.models import Category, CategoryRule, Policy, Setting, MLModel, InferenceArtifact


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()
                if not re.search(r"password|secret|token|api_key|credential|backup|history", k, re.I)}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str) and ("://" in value and "@" in value or value.startswith("/home/")):
        return ""
    return value


with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    if Category.objects.filter(reference_id__isnull=False).exists():
        raise RuntimeError("Reference-backed categories require explicit safe reference export")
    objects = list(Category.objects.all()) + list(CategoryRule.objects.all()) + list(Policy.objects.all())
    allowed = {"detectors", "normalizer", "semantic_detection", "horizon_detection", "ocr",
               "retention", "performance_deployment", "llm_analyzer", "integrations"}
    for setting in Setting.objects.all():
        if setting.key in allowed or setting.key.startswith("ui:"):
            setting.value = sanitize(setting.value)
            objects.append(setting)
    for model in MLModel.objects.all():
        model.dataset_id = None
        model.metrics = {k: v for k, v in model.metrics.items() if k == "threshold"}
        objects.append(model)
    objects.extend(InferenceArtifact.objects.all())
    print(serializers.serialize("json", objects))