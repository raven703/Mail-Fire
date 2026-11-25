"""Snapshot ORM configuration; evaluate proven algorithms in secret-free sandbox."""

from records.models import Category, CategoryRule, Reference, Setting


def configuration():
    settings = {row.pk: row.value for row in Setting.objects.filter(pk__in=["normalizer", "detectors"])}
    groups = {}
    for rule in CategoryRule.objects.filter(enabled=True, category__active=True).select_related("category").order_by(
        "priority", "created_at", "id"
    ):
        category = rule.category
        bucket = groups.setdefault(category.pk, {
            "category": {"id": category.pk, "name": category.name, "mode": category.mode, "match_mode": category.match_mode},
            "rules": [],
        })
        bucket["rules"].append({
            "id": rule.pk, "kind": rule.kind, "title": rule.title, "risk": rule.risk, "config": rule.config,
            "version": str(rule.created_at.isoformat()),
        })
    return {
        "inactive_categories": list(Category.objects.filter(active=False).values_list("pk", flat=True)),
        "settings": settings,
        "groups": list(groups.values()),
        "references": list(Reference.objects.values("id", "text", "fingerprint")),
    }