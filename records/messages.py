"""Message and delivery-import workspace, with content gated independently."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from records.models import ImportRecord, Incident, Message
from records.ui_filters import filter_dates, pagination_query
from records.workspace import access


@require_GET
def messages(request):
    error = access(request)
    if error is not None:
        return error
    rows = filter_dates(Message.objects.all(), request.GET).order_by("-created_at", "-pk")
    query, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if status in {"PENDING", "ANALYZED", "PARTIAL", "FAILED"}:
        rows = rows.filter(status=status)
    if query:
        criteria = Q(pk=query)
        if request.user.has_perm("identity.view_originals"):
            criteria |= Q(subject__icontains=query) | Q(sender__icontains=query)
        rows = rows.filter(criteria)
    return render(request, "records/messages.html", {
        "page": Paginator(rows, 50).get_page(request.GET.get("page")), "query": query, "status": status,
        "pagination_query": pagination_query(request.GET),
    })


@require_GET
def imports(request):
    error = access(request, write=True)
    if error is not None:
        return error
    rows = ImportRecord.objects.select_related("message").order_by("-created_at", "-pk")
    return render(request, "records/imports.html", {"page": Paginator(rows, 50).get_page(request.GET.get("page"))})


@require_GET
def overview(request):
    error = access(request)
    if error is not None:
        return error
    try:
        days = int(request.GET.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    since = timezone.now() - timedelta(days=days)
    messages = Message.objects.filter(created_at__gte=since)
    incidents = Incident.objects.filter(created_at__gte=since)
    daily = list(messages.annotate(day=TruncDay("created_at")).values("day").annotate(count=Count("pk")).order_by("day"))
    return render(request, "records/overview.html", {
        "days": days,
        "message_statuses": messages.values("status").annotate(count=Count("pk")).order_by("status"),
        "incident_statuses": incidents.values("status").annotate(count=Count("pk")).order_by("status"),
        "daily": daily, "daily_max": max((row["count"] for row in daily), default=1),
        "risk": incidents.aggregate(average=Avg("risk")),
        "high_risk": incidents.filter(risk__gte=75).count(),
        "policies": incidents.values("policy__name").annotate(count=Count("pk")).order_by("-count")[:20],
        "analysts": incidents.values("assignee_ref__username").annotate(count=Count("pk")).order_by("-count")[:20],
        "unassigned": Incident.objects.filter(assignee_ref__isnull=True).exclude(status__in=["CLOSED", "FALSE_POSITIVE"]).count(),
        "held": Message.objects.filter(legal_hold=True).count(),
        "pending": Message.objects.filter(status="PENDING").count(),
    })