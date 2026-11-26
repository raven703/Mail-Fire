"""Read-only presentation helpers; no rule evaluation or form mutation."""
from django import template
from django.db.models import Count, Q

from records.models import CategoryRule

register = template.Library()


@register.simple_tag
def category_rule_counts(categories):
    return dict(CategoryRule.objects.filter(category_id__in=[row.pk for row in categories]).filter(
                    ~Q(category__mode="builtin") | Q(config__builtin_context=True))
                .values_list("category_id").annotate(total=Count("pk")))


@register.filter
def lookup(values, key):
    return values.get(key, 0)

@register.simple_tag
def detection_method(category, count=0):
    from app.category_catalog import detector_name
    if category.mode == "builtin":
        label = detector_name(category.pk) or "Встроенный детектор"
        return label + (" + правила контекста" if count else "")
    if category.mode == "ml":
        return "ML (выключен)" + (" / правила" if count else "")
    return "Правила"


@register.simple_tag
def category_context_supported(category):
    from app.category_catalog import CONTEXT_CATEGORIES
    return category.mode == "builtin" and category.pk in CONTEXT_CATEGORIES
