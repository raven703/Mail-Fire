"""Explicit, backed-up replacement of one managed RU3 category."""
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from policy_engine.ru3 import PII_CATEGORY, METADATA, candidate, snapshot, write_backup
from records.models import Audit, Category, CategoryRule, Setting

BASELINE_SHA = "264cf40da0d55dd34f09b627b0aa157ed44feca9a57d23a06e64ea9fe05b041d"
BASELINE = "config/rulepacks/history/ru3_pii_before_calibration.json"


def old_specs():
    cat = json.loads((settings.BASE_DIR / BASELINE).read_text())
    return [{"id": str(uuid5(NAMESPACE_URL, f"mice:ru3:{cat['id']}:{i}")),
             "category_id": cat["id"], "config": {k: v for k, v in rule.items() if k not in METADATA},
             **{k: rule[k] for k in METADATA}} for i, rule in enumerate(cat["rules"])]


@transaction.atomic
def apply_pii(*, apply=False, backup_dir=None):
    pack, rules, digest = candidate()
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE categories, category_rules, policies, settings IN SHARE ROW EXCLUSIVE MODE")
    marker = Setting.objects.filter(pk="dlp_rulepack").first()
    if not marker or marker.value.get("name") != "RU3":
        raise ValueError("Managed RU3 must be installed first")
    if marker.value.get("sha256") == digest:
        return {"already_applied": True, "applied": False, "sha256": digest}
    if marker.value.get("sha256") != BASELINE_SHA:
        raise ValueError("Unknown RU3 baseline; review locally")
    old = old_specs()
    rows = {r.pk: r for r in CategoryRule.objects.filter(category_id=PII_CATEGORY)}
    if set(rows) != {r["id"] for r in old}:
        raise ValueError("PII rule catalog changed locally; review before replacement")
    for spec in old:
        row = rows[spec["id"]]
        if any(getattr(row, k) != v for k, v in spec.items() if k != "id"):
            raise ValueError("PII rule changed locally: " + spec["id"])
    replacement = [r for r in rules if r["category_id"] == PII_CATEGORY]
    keep = {r["id"] for r in replacement} & set(rows)
    new = [r for r in replacement if r["id"] not in keep]
    if CategoryRule.all_objects.filter(pk__in=[r["id"] for r in new]).exists():
        raise ValueError("Replacement rule identity already exists")
    report = {"applied": apply, "category": PII_CATEGORY, "retained": len(keep),
              "archived": len(rows)-len(keep), "created": len(new), "sha256": digest}
    if not apply:
        return report
    if not backup_dir:
        raise ValueError("Durable backup directory required")
    path, sha = write_backup(backup_dir, snapshot())
    report.update(backup=path, backup_sha256=sha)
    for identifier, row in rows.items():
        if identifier in keep:
            continue
        row.enabled = False
        row.deleted_at = timezone.now()
        row.save(update_fields=["enabled", "deleted_at"])
        Audit.objects.create(actor="system:ru3", action="rule_delete", target=row.pk,
                             details={"category_id": PII_CATEGORY, "title": row.title,
                                      "kind": row.kind, "risk": row.risk, "config": row.config})
    for spec in new:
        CategoryRule.objects.create(pk=spec["id"], **{k: v for k, v in spec.items() if k != "id"})
    # Preserve category activation, policies and any custom category metadata.
    expected = {r["id"] for r in replacement}
    if set(CategoryRule.objects.filter(category_id=PII_CATEGORY).values_list("pk", flat=True)) != expected:
        raise ValueError("PII active rule verification failed")
    marker.value = {**marker.value, "sha256": digest, "pii_calibration_backup": path,
                    "pii_calibration_backup_sha256": sha}
    marker.save(update_fields=["value"])
    Audit.objects.create(actor="system:ru3", action="dlp_ru3_pii_calibration",
                         target=PII_CATEGORY, details=report)
    return report
