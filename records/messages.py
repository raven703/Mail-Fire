"""Message and delivery-import workspace, with content gated independently."""

import csv
from collections import Counter
from datetime import timedelta
from uuid import uuid4

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from records.models import Attachment, ImportRecord, Incident, MailEvent, Message
from records.ui_filters import filter_dates, pagination_query
from records.workspace import access


@require_GET
def messages(request):
    error = access(request)
    if error is not None:
        return error
    rows = filter_dates(Message.objects.all(), request.GET).order_by("-created_at", "-pk")
    events = MailEvent.objects.all()
    direction, source = request.GET.get("direction", ""), request.GET.get("source", "")
    if direction:
        events = events.filter(direction=direction)
    if source:
        events = events.filter(source=source)
    if direction or source:
        rows = rows.filter(pk__in=events.values("message_id"))
    query, status = request.GET.get("q", "").strip(), request.GET.get("status", "")
    if status in {"PENDING", "ANALYZED", "PARTIAL", "FAILED"}:
        rows = rows.filter(status=status)
    if query:
        criteria = Q(pk=query)
        if request.user.has_perm("identity.view_originals"):
            criteria |= Q(subject__icontains=query) | Q(sender__icontains=query)
        rows = rows.filter(criteria)
    for parameter, model in (("attachments", Attachment), ("incidents", Incident)):
        value = request.GET.get(parameter)
        identifiers = model.objects.values("message_id")
        if value == "yes":
            rows = rows.filter(pk__in=identifiers)
        elif value == "no":
            rows = rows.exclude(pk__in=identifiers)
    mime = request.GET.get("mime", "").strip()
    if mime:
        rows = rows.filter(pk__in=Attachment.objects.filter(mime__icontains=mime).values("message_id"))
    sort = {"date": "created_at", "sender": "sender"}.get(request.GET.get("sort"), "created_at")
    if sort == "sender" and not request.user.has_perm("identity.view_originals"):
        sort = "created_at"
    rows = rows.order_by(("" if request.GET.get("order") == "asc" else "-") + sort, "pk")
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    identifiers = [row.pk for row in page]
    counts = {}
    deliveries = {}
    for event in MailEvent.objects.filter(message_id__in=identifiers).order_by("created_at", "pk"):
        deliveries[event.message_id] = event
    for model, key in ((Attachment, "attachment_count"), (Incident, "incident_count")):
        for row in model.objects.filter(message_id__in=identifiers).values("message_id").annotate(total=Count("pk")):
            counts.setdefault(row["message_id"], {})[key] = row["total"]
    for row in page:
        row.attachment_count = counts.get(row.pk, {}).get("attachment_count", 0)
        row.incident_count = counts.get(row.pk, {}).get("incident_count", 0)
        row.delivery = deliveries.get(row.pk)
    return render(request, "records/messages.html", {
        "page": page, "query": query, "status": status,
        "request_token": uuid4().hex,
        "pagination_query": pagination_query(request.GET),
        "sources": MailEvent.objects.values_list("source", flat=True).distinct().order_by("source"),
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
    timeline = list(incidents.annotate(day=TruncDay("created_at")).values("day").annotate(
        high=Count("pk", filter=Q(risk__gte=75)), medium=Count("pk", filter=Q(risk__gte=40, risk__lt=75)),
        low=Count("pk", filter=Q(risk__lt=40))).order_by("day"))
    timeline_max = max(1, max((row["high"] + row["medium"] + row["low"] for row in timeline), default=0))
    for row in timeline:
        row["segments"] = [{"level": level.upper(), "count": row[level], "height": round(row[level] / timeline_max * 150)}
                           for level in ("low", "medium", "high")]
    if request.GET.get("export") == "timeline":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="mailfire-incidents.csv"'
        response["Cache-Control"] = "no-store"
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Время", "HIGH", "MEDIUM", "LOW"])
        for row in timeline:
            writer.writerow([row["day"].isoformat(), row["high"], row["medium"], row["low"]])
        return response
    category_counts = Counter()
    for group in incidents.values("categories").annotate(total=Count("pk")):
        for category in set(group["categories"] or []):
            category_counts[category] += group["total"]
    category_max = max(category_counts.values(), default=1)
    from pipeline.models import WorkItem
    from pipeline.monitoring import service_snapshot
    risk_bands = [
        {"label": "Высокий", "key": "high", "count": incidents.filter(risk__gte=75).count()},
        {"label": "Средний", "key": "medium", "count": incidents.filter(risk__gte=40, risk__lt=75).count()},
        {"label": "Низкий", "key": "low", "count": incidents.filter(risk__lt=40).count()},
    ]
    return render(request, "records/overview.html", {
        "days": days,
        "timeline": timeline,
        "analytics_categories": [{"name": name, "count": count, "percent": round(count / category_max * 100)}
                                 for name, count in category_counts.most_common()],
        "analytics_total": incidents.count(),
        "analytics_review": incidents.exclude(status__in=["CLOSED", "FALSE_POSITIVE"]).count(),
        "analytics_analyzed": messages.filter(status="ANALYZED").count(),
        "analytics_jobs": WorkItem.objects.filter(status="RUNNING").count(),
        "analytics_services": service_snapshot(),
        "risk_bands": risk_bands,
        "priority_incidents": incidents.select_related("message", "assignee_ref").exclude(status__in=["CLOSED", "FALSE_POSITIVE"]).order_by("-risk", "-created_at")[:8],
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