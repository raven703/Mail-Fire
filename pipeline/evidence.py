"""Snapshot ORM configuration; evaluate proven algorithms in secret-free sandbox."""

from records.models import CategoryRule, Reference, Setting


def configuration():
    settings = {row.pk: row.value for row in Setting.objects.filter(pk__in=["normalizer", "detectors"])}
    groups = {}
    for rule in CategoryRule.objects.filter(enabled=True, category__active=True).select_related("category").order_by(
        "priority", "created_at", "id"
    ):
        category = rule.category
        bucket = groups.setdefault(category.pk, {
            "category": {"id": category.pk, "mode": category.mode, "match_mode": category.match_mode},
            "rules": [],
        })
        bucket["rules"].append({
            "id": rule.pk, "kind": rule.kind, "title": rule.title, "risk": rule.risk, "config": rule.config,
        })
    return {
        "settings": settings,
        "groups": list(groups.values()),
        "references": list(Reference.objects.values("id", "text", "fingerprint")),
    }