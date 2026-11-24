"""Shared date range contract for native investigation lists."""
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def filter_dates(rows, params):
    for parameter, lookup in (("start", "created_at__gte"), ("end", "created_at__lte")):
        try:
            value = parse_datetime(params.get(parameter, ""))
        except ValueError:
            value = None
        if value:
            if timezone.is_naive(value):
                value = timezone.make_aware(value)
            rows = rows.filter(**{lookup: value})
    return rows


def pagination_query(params):
    values = params.copy()
    values.pop("page", None)
    return values.urlencode()