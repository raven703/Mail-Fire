"""Message and delivery-import workspace, with content gated independently."""

from uuid import uuid4

from django.contrib.postgres.search import SearchQuery, SearchVector
from django.core.paginator import Paginator
from django.db.models import CharField, Count, F, OuterRef, Q, Subquery
from django.db.models.functions import Cast
from django.shortcuts import render
from django.views.decorators.http import require_GET

from records.processing_status import describe, latest_jobs
from records.models import Attachment, Content, ImportRecord, Incident, MailEvent, Message
from records.ui_filters import filter_dates, list_period, pagination_query, resolve_period
from records.workspace import HIGH_RISK, MEDIUM_RISK, access, severity


@require_GET
def messages(request):
    error = access(request)
    if error is not None:
        return error
    resolve_period(request)
    rows = filter_dates(Message.objects.defer("headers", "error"), list_period(request.GET))
    risks = Incident.objects.filter(message_id=OuterRef("pk")).values("risk")
    rows = rows.annotate(incident_risk=Subquery(risks[:1]))
    events = MailEvent.objects.all()
    direction, source = request.GET.get("direction", ""), request.GET.get("source", "")
    if direction:
        events = events.filter(direction=direction)
    if source in {"eml", "msg"}:
        rows = rows.filter(format=source)
    elif source:
        events = events.filter(source=source)
    if direction or source and source not in {"eml", "msg"}:
        rows = rows.filter(pk__in=events.values("message_id"))
    query, status = request.GET.get("q", "").strip()[:500], request.GET.get("status", "")
    if status == "INCOMPLETE":
        rows = rows.filter(status__in=["PARTIAL", "FAILED"])
    elif status in {"PENDING", "ANALYZED", "PARTIAL", "FAILED"}:
        rows = rows.filter(status=status)
    if query:
        criteria = Q(pk=query)
        if request.user.has_perm("identity.view_originals"):
            rows = rows.alias(recipient_search=Cast("recipients", CharField()), header_search=Cast("headers", CharField()))
            content = Content.objects.alias(fts=SearchVector("text", config="simple")).filter(
                Q(text__icontains=query) | Q(fts=SearchQuery(query, config="simple")),
            )
            criteria |= (Q(subject__icontains=query) | Q(sender__icontains=query) | Q(recipient_search__icontains=query)
                         | Q(header_search__icontains=query) | Q(content_id__in=content.values("pk"))
                         | Q(pk__in=Attachment.objects.filter(name__icontains=query).values("message_id")))
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
    levels = {"high": Q(incident_risk__gte=HIGH_RISK),
              "medium": Q(incident_risk__gte=MEDIUM_RISK, incident_risk__lt=HIGH_RISK),
              "low": Q(incident_risk__lt=MEDIUM_RISK)}
    if request.GET.get("severity") in levels:
        rows = rows.filter(levels[request.GET["severity"]])
    sort = {"date": "created_at", "sender": "sender", "subject": "subject",
            "risk": "incident_risk"}.get(request.GET.get("sort"), "created_at")
    if sort in {"sender", "subject"} and not request.user.has_perm("identity.view_originals"):
        sort = "created_at"
    column = F(sort)
    order = column.asc(nulls_last=True) if request.GET.get("order") == "asc" else column.desc(nulls_last=True)
    rows = rows.order_by(order, "pk")
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    identifiers = [row.pk for row in page]
    counts = {}
    deliveries = {}
    for event in MailEvent.objects.filter(message_id__in=identifiers).order_by("created_at", "pk"):
        deliveries.setdefault(event.message_id, event)
    for model, key in ((Attachment, "attachment_count"), (Incident, "incident_count")):
        for row in model.objects.filter(message_id__in=identifiers).values("message_id").annotate(total=Count("pk")):
            counts.setdefault(row["message_id"], {})[key] = row["total"]
    jobs = latest_jobs(page)
    for row in page:
        row.processing = describe(row, jobs.get(row.pk))
        row.attachment_count = counts.get(row.pk, {}).get("attachment_count", 0)
        row.incident_count = counts.get(row.pk, {}).get("incident_count", 0)
        row.delivery = deliveries.get(row.pk)
        row.severity = severity(row.incident_risk) if row.incident_risk is not None else ""
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
