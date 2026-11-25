"""Read-only presentation helpers; no rule evaluation or form mutation."""
from django import template
from django.db.models import Count

from records.models import CategoryRule

register = template.Library()


@register.simple_tag
def category_rule_counts(categories):
    return dict(CategoryRule.objects.filter(category_id__in=[row.pk for row in categories])
                .values_list("category_id").annotate(total=Count("pk")))


@register.filter
def lookup(values, key):
    return values.get(key, 0)