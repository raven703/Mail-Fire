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
BASELINES = {
    "pack-ru2-customer-data": "config/rulepacks/history/ru3_customer_before_calibration.json",
    "pack-ru2-pricing": "config/rulepacks/history/ru3_pricing_before_calibration.json",
    "pack-ru2-financial-plans": "config/rulepacks/history/ru3_financial_before_calibration.json",
    PII_CATEGORY: "config/rulepacks/history/ru3_pii_before_calibration.json",
    "pack-ru2-internal-docs": "config/rulepacks/history/ru3_internal_before_calibration.json",
}



def old_specs(category_id):
    cat = json.loads((settings.BASE_DIR / BASELINES[category_id]).read_text())
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
    rows, replacement, keep, new = {}, [], set(), []
    for category_id in BASELINES:
        old = old_specs(category_id)
        current = {r.pk: r for r in CategoryRule.objects.filter(category_id=category_id)}
        target = [r for r in rules if r["category_id"] == category_id]
        if set(current) != {r["id"] for r in old}:
            raise ValueError("Rule catalog changed locally: " + category_id)
        for spec in old:
            row = current[spec["id"]]
            if any(getattr(row, k) != v for k, v in spec.items() if k != "id"):
                raise ValueError("Rule changed locally: " + spec["id"])
        rows.update(current)
        replacement.extend(target)
    keep = {r["id"] for r in replacement} & set(rows)
    new = [r for r in replacement if r["id"] not in keep]
    if CategoryRule.all_objects.filter(pk__in=[r["id"] for r in new]).exists():
        raise ValueError("Replacement rule identity already exists")
    report = {"applied": apply, "categories": list(BASELINES), "retained": len(keep),
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
                             details={"category_id": row.category_id, "title": row.title,
                                      "kind": row.kind, "risk": row.risk, "config": row.config})
    for spec in new:
        CategoryRule.objects.create(pk=spec["id"], **{k: v for k, v in spec.items() if k != "id"})
    # Preserve category activation, policies and any custom category metadata.
    expected = {r["id"] for r in replacement}
    if set(CategoryRule.objects.filter(category_id__in=BASELINES).values_list("pk", flat=True)) != expected:
        raise ValueError("Calibrated active rule verification failed")
    marker.value = {**marker.value, "sha256": digest, "pii_calibration_backup": path,
                    "pii_calibration_backup_sha256": sha}
    marker.save(update_fields=["value"])
    Audit.objects.create(actor="system:ru3", action="dlp_ru3_calibration",
                         target="RU3", details=report)
    return report
