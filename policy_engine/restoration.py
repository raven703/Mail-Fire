"""Lossless DLP restoration from the benchmark snapshot and its RU2 rule source."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import connection, transaction
from django.utils.dateparse import parse_datetime

from policy_engine.rule_config import validate_config
from records.models import Category, CategoryRule, Policy, Setting

SNAPSHOT = "test-data/results-benchmark350-20261123/config.json"
RULEPACK = "config/rulepacks/ru2_morph_weighted_rules.json"
METADATA = {"kind", "title", "enabled", "risk", "priority"}


def load_configuration(snapshot=None, rulepack=None):
    snapshot = Path(snapshot or settings.BASE_DIR / SNAPSHOT)
    rulepack = Path(rulepack or settings.BASE_DIR / RULEPACK)
    source = json.loads(snapshot.read_text())
    pack = json.loads(rulepack.read_text())
    categories = source["categories"]
    custom = {row["id"] for row in categories if row["mode"] not in {"builtin", "label"}}
    pack_ids = [row["id"] for row in pack["categories"]]
    if custom != set(pack_ids) or len(pack_ids) != len(set(pack_ids)):
        raise ValueError("Snapshot/RU2 category IDs differ")
    rules = []
    for category in pack["categories"]:
        for index, rule in enumerate(category["rules"]):
            config = {key: value for key, value in rule.items() if key not in METADATA}
            # Validate without normalizing, sorting or adding defaults to source JSON.
            validate_config(rule["kind"], config)
            rules.append({
                "id": str(uuid5(NAMESPACE_URL, f"mice:original-dlp:{category['id']}:{index}:{rule['title']}")),
                "category_id": category["id"],
                **{key: rule[key] for key in METADATA}, "config": config,
            })
    policies = [{**row, "created_at": parse_datetime(row["created_at"])} for row in source["policies"]]
    detectors = [row for row in source["settings"] if row["key"] == "detectors"]
    if len(detectors) != 1:
        raise ValueError("Expected exactly one detector configuration")
    for rows in (categories, rules, policies):
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError("Duplicate source IDs")
    known = {row["id"] for row in categories}
    if any(set(row["conditions"].get("categories", [])) - known for row in policies):
        raise ValueError("Unknown policy category")
    return {"categories": categories, "rules": rules, "policies": policies,
            "detectors": detectors[0], "sources": {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (snapshot, rulepack)}}


def compare(expected):
    differences = []
    for key, model in (("categories", Category), ("rules", CategoryRule), ("policies", Policy)):
        for spec in expected[key]:
            row = model.objects.filter(pk=spec["id"]).first()
            for field, value in spec.items():
                if row is None or getattr(row, field) != value:
                    differences.append(f"{key}/{spec['id']}/{field}")
    detector = Setting.objects.filter(pk="detectors").first()
    if detector is None or detector.value != expected["detectors"]["value"]:
        differences.append("settings/detectors")
    extras = {
        key: sorted(model.objects.exclude(pk__in=[r["id"] for r in expected[key]]).values_list("pk", flat=True))
        for key, model in (("categories", Category), ("rules", CategoryRule), ("policies", Policy))
    }
    rules = expected["rules"]
    return {"differences": differences, "extras": extras,
            "system_categories": sum(c["mode"] in {"builtin", "label"} for c in expected["categories"]),
            "custom_categories": sum(c["mode"] not in {"builtin", "label"} for c in expected["categories"]),
            "rules_by_type": dict(Counter(r["kind"] for r in rules)),
            "keyword_modes": dict(Counter(r["config"].get("match_type", "substring") for r in rules if r["kind"] == "keywords")),
            "weighted_terms": sum(len(r["config"].get("terms", [])) for r in rules),
            "policies": [{"id": p["id"], "name": p["name"], "priority": p["priority"],
                          "min_risk": p["conditions"]["min_risk"]} for p in expected["policies"]],
            "sources": expected["sources"]}


@transaction.atomic
def restore(expected):
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE categories, category_rules, policies, settings IN SHARE ROW EXCLUSIVE MODE")
    for key, model in (("categories", Category), ("rules", CategoryRule), ("policies", Policy)):
        for spec in expected[key]:
            model.objects.update_or_create(pk=spec["id"], defaults={k: v for k, v in spec.items() if k != "id"})
    Setting.objects.update_or_create(pk="detectors", defaults={"value": expected["detectors"]["value"]})
    result = compare(expected)
    if result["differences"]:
        raise ValueError("Restoration verification failed: " + str(result["differences"]))
    return result