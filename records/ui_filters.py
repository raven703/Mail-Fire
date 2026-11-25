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


def resolve_period(request):
    """One session-backed period contract; invalid input never replaces state."""
    from django.http import QueryDict

    def valid(params):
        if params.get("range") in ROLLING_HOURS:
            return {"range": params["range"]}
        start, end = period_bounds(params)
        if start and end and start < end:
            return {"range": "custom", "start": start.isoformat(), "end": end.isoformat()}
        return None

    explicit = any(key in request.GET for key in DATE_PARAMETERS)
    selected = valid(request.GET) if explicit else None
    session = getattr(request, "session", {})
    if selected and not request.headers.get("X-MICE-Period-Poll") and session.get("mice_period") != selected:
        session["mice_period"] = selected
    selected = selected or valid(session.get("mice_period", {})) or {"range": "24"}
    params = request.GET.copy()
    for key in DATE_PARAMETERS:
        params.pop(key, None)
    params.update(selected)
    request.GET = params
    dates = QueryDict(mutable=True)
    dates.update(selected)
    request.mice_period = dates
    return dates
