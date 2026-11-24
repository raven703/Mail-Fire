"""Message and delivery-import workspace, with content gated independently."""

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.views.decorators.http import require_GET

from records.models import ImportRecord, Incident, Message
from records.workspace import access


@require_GET
def messages(request):
    error = access(request)
    if error is not None:
        return error
    rows = Message.objects.order_by("-created_at", "-pk")
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
    return render(request, "records/overview.html", {
        "message_statuses": Message.objects.values("status").annotate(count=Count("pk")).order_by("status"),
        "incident_statuses": Incident.objects.values("status").annotate(count=Count("pk")).order_by("status"),
        "unassigned": Incident.objects.filter(assignee_ref__isnull=True).exclude(status__in=["CLOSED", "FALSE_POSITIVE"]).count(),
        "held": Message.objects.filter(legal_hold=True).count(),
        "pending": Message.objects.filter(status="PENDING").count(),
    })