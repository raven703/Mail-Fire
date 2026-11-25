"""Atomic RU3 replacement with durable pre-update backup and archived rules."""

import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from policy_engine.catalog_service import revision
from policy_engine.rule_config import validate_config
from records.models import Audit, Category, CategoryRule, Policy, Setting

PACK = "config/rulepacks/ru3_candidate.json"
METADATA = {"kind", "title", "enabled", "risk", "priority"}
ALIASES = {"RU_INN": "INN", "RU_PHONE": "PHONE"}


def candidate():
    raw = (settings.BASE_DIR / PACK).read_bytes()
    pack = json.loads(raw)
    rules = []
    for category in pack["categories"]:
        for index, rule in enumerate(category["rules"]):
            config = {k: v for k, v in rule.items() if k not in METADATA}
            validate_config(rule["kind"], config)
            rules.append({"id": str(uuid5(NAMESPACE_URL, f"mice:ru3:{category['id']}:{index}")),
                          "category_id": category["id"], "config": config,
                          **{k: rule[k] for k in METADATA}})
    if (len(pack["categories"]), len(rules), sum(len(r["config"].get("terms", [])) for r in rules),
            len(pack["policies"])) != (12, 36, 223, 8):
        raise ValueError("Unexpected RU3 category/rule/term/policy counts")
    if len({c["id"] for c in pack["categories"]}) != 12 or len({p["name"] for p in pack["policies"]}) != 8:
        raise ValueError("Duplicate RU3 category or policy")
    return pack, rules, hashlib.sha256(raw).hexdigest()


def canonical_conditions(value):
    value = dict(value)
    if "categories" in value:
        value["categories"] = list(dict.fromkeys(ALIASES.get(c, c) for c in value["categories"]))
    return value


def snapshot():
    return {"schema": 1, "categories": list(Category.objects.order_by("pk").values()),
            "rules": list(CategoryRule.all_objects.order_by("pk").values()),
            "policies": list(Policy.objects.order_by("pk").values()),
            "settings": list(Setting.objects.filter(pk__in=["detectors", "normalizer", "dlp_rulepack"]).order_by("pk").values())}


def write_backup(directory, value):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, sort_keys=True, indent=2).encode()
    digest = hashlib.sha256(data).hexdigest()
    path = directory / f"dlp-before-ru3-{digest}.json"
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("DLP backup verification failed")
    return str(path), digest


@transaction.atomic
def upgrade(*, backup_dir, apply=False):
    pack, rules, digest = candidate()
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE categories, category_rules, policies, settings IN SHARE ROW EXCLUSIVE MODE")
    marker = Setting.objects.filter(pk="dlp_rulepack").first()
    if marker and marker.value.get("sha256") == digest:
        return {"applied": False, "already_applied": True, "sha256": digest}
    if marker:
        raise ValueError("A different managed DLP pack is installed; explicit upgrade review required")
    names = [p["name"] for p in pack["policies"]]
    if any(Policy.objects.filter(name=name).count() > 1 for name in names):
        raise ValueError("Ambiguous existing policy name")
    report = {"applied": apply, "categories": 12, "rules": 36, "weighted_terms": 223,
              "policies": 8, "sha256": digest}
    if not apply:
        return report
    path, backup_sha = write_backup(backup_dir, snapshot())
    report.update(backup=path, backup_sha256=backup_sha)
    ids = [c["id"] for c in pack["categories"]]
    # Preserve legacy rule descriptions in a durable configuration archive. This
    # supplements per-analysis snapshots without touching historical findings.
    Setting.objects.create(pk="dlp_ru2_history", value={"backup_sha256": backup_sha,
        "categories": {c.pk: c.name for c in Category.objects.filter(pk__in=ids)},
        "rules": {r.pk: {"id": r.pk, "kind": r.kind, "title": r.title, "risk": r.risk,
                          "config": r.config, "version": r.created_at.isoformat()}
                  for r in CategoryRule.all_objects.filter(category_id__in=ids)}})
    for row in CategoryRule.objects.filter(category_id__in=ids):
        row.deleted_at = timezone.now()
        row.enabled = False
        row.save(update_fields=["deleted_at", "enabled"])
        Audit.objects.create(actor="system:ru3", action="rule_delete", target=row.pk,
                             details={"pack": "RU3", "title": row.title, "kind": row.kind,
                                      "risk": row.risk, "config": row.config, "category_id": row.category_id})
    for spec in pack["categories"]:
        existing = Category.objects.filter(pk=spec["id"]).first()
        fields = {k: spec[k] for k in ("group_name", "description", "match_mode")}
        fields.update(name=spec["name"].replace("[RU2]", "[RU3]"), mode="custom")
        if not existing:
            fields["active"] = spec["active"]
        Category.objects.update_or_create(pk=spec["id"], defaults=fields)
    for spec in rules:
        CategoryRule.all_objects.update_or_create(pk=spec["id"], defaults={
            **{k: v for k, v in spec.items() if k != "id"}, "deleted_at": None})
    for old, new in ALIASES.items():
        Category.objects.filter(pk=old).update(active=False)
        Category.objects.filter(pk=new).update(name="ИНН" if new == "INN" else "Телефон")
    condition_keys = {"senders", "min_risk", "direction", "min_count", "categories", "category_match"}
    for spec in pack["policies"]:
        row = Policy.objects.filter(name=spec["name"]).first()
        conditions = canonical_conditions({k: spec[k] for k in condition_keys})
        if row:
            revision(row)
            row.conditions = {**row.conditions, **conditions}
            row.version += 1
        else:
            row = Policy(name=spec["name"], conditions=conditions, enabled=spec["enabled"],
                         shadow=spec["shadow"], priority=spec["priority"])
        row.save()
        revision(row)
    for row in Policy.objects.all():
        canonical = canonical_conditions(row.conditions)
        if canonical != row.conditions:
            revision(row)
            row.conditions = canonical
            row.version += 1
            row.save(update_fields=["conditions", "version"])
            revision(row)
    if CategoryRule.objects.filter(category_id__in=ids).count() != 36:
        raise ValueError("RU3 active rule verification failed")
    Setting.objects.create(pk="dlp_rulepack", value={"name": "RU3", "sha256": digest,
                           "backup": path, "backup_sha256": backup_sha})
    Audit.objects.create(actor="system:ru3", action="dlp_ru3_upgrade", target="RU3", details=report)
    return report