"""Message and delivery-import workspace, with content gated independently."""

from uuid import uuid4

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
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
