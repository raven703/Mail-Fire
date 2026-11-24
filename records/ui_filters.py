"""Shared date range contract for native investigation lists and analytics."""
from datetime import timedelta
from datetime import timezone as fixed_timezone

from django.utils import timezone
from django.utils.dateparse import parse_datetime

ROLLING_HOURS = {"24", "168", "720"}
DATE_PARAMETERS = ("range", "start", "end", "start_offset", "end_offset")


def date_parameter(params, key):
    try:
        value = parse_datetime(params.get(key, ""))
        if value and timezone.is_naive(value):
            offset = int(params.get(key + "_offset") or 0)
            if not -840 <= offset <= 840:
                return None
            value = value.replace(tzinfo=fixed_timezone(timedelta(minutes=offset)))
        return value
    except (TypeError, ValueError):
        return None


def period_bounds(params, now=None):
    if params.get("range") in ROLLING_HOURS:
        end = now or timezone.now()
        if timezone.is_naive(end):
            end = end.replace(tzinfo=fixed_timezone.utc)
        return end - timedelta(hours=int(params["range"])), end
    return date_parameter(params, "start"), date_parameter(params, "end")


def list_period(params):
    return params if any(params.get(key) for key in ("range", "start", "end")) else {"range": "24"}


def filter_dates(rows, params):
    start, end = period_bounds(params)
    if start:
        rows = rows.filter(created_at__gte=start)
    if end:
        rows = rows.filter(created_at__lt=end)
    return rows


def pagination_query(params):
    values = params.copy()
    values.pop("page", None)
    return values.urlencode()
