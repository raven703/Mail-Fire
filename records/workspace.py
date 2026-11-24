"""Native analyst workspace and transactional investigation actions."""

from uuid import uuid4

from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from identity.models import User
from policy_engine.service import EvidenceUnavailable, request_evaluation
from records.models import Attachment, Audit, Comment, Incident, MailEvent, Message
from records.ui_filters import filter_dates, pagination_query

STATUSES = ("NEW", "ASSIGNED", "REVIEW", "CONFIRMED", "FALSE_POSITIVE", "CLOSED", "REOPENED")


class InvestigationForm(forms.Form):
    status = forms.ChoiceField(choices=[(value, value) for value in STATUSES], label="Статус")
    assignee = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Аналитик")
    comment = forms.CharField(max_length=10000, required=False, widget=forms.Textarea, label="Комментарий")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(is_active=True, role__in=["admin", "analyst"]).order_by("username")


def access(request, *, write=False, originals=False):
    if not request.user.is_authenticated:
        return redirect("login-page")
    permission = "identity.view_originals" if originals else "identity.investigate" if write else "identity.access_mice"
    if not request.user.has_perm(permission):
        return HttpResponseForbidden("Недостаточно прав")
    return None


@transaction.atomic
def update_investigation(actor, incident_id, *, status, assignee=None, comment=""):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    if not actor.has_perm("identity.investigate"):
        raise PermissionError("Недостаточно прав")
    if status not in STATUSES or len(comment) > 10000:
        raise ValueError("Некорректное решение")
    row = Incident.objects.select_for_update().get(pk=incident_id)
    if assignee:
        target = User.objects.select_for_update().get(pk=assignee.pk)
        if not target.is_active or target.role not in {"admin", "analyst"}:
            raise ValueError("Выберите действующего аналитика")
    before = {"status": row.status, "assignee": row.assignee_ref_id}
    row.status, row.assignee_ref_id = status, assignee.pk if assignee else None
    row.save(update_fields=["status", "assignee_ref"])
    if comment.strip():
        Comment.objects.create(incident=row, account_id=actor.pk, text=comment.strip())
    Audit.objects.create(
        actor=actor.pk, action="incident_decision", target=row.pk,
        details={"before": before, "status": status, "assignee": row.assignee_ref_id},
    )
    return row


@require_GET
def incidents(request):
    error = access(request)
    if error is not None:
        return error
    rows = filter_dates(Incident.objects.select_related("message", "assignee_ref"), request.GET).order_by("-created_at", "-pk")
    query, status, assignee = (request.GET.get(key, "").strip() for key in ("q", "status", "assignee"))
    if request.GET.get("severity") == "high":
        rows = rows.filter(risk__gte=75)
    if query:
        criteria = Q(pk=query) | Q(message_id=query)
        if request.user.has_perm("identity.view_originals"):
            criteria |= Q(message__subject__icontains=query) | Q(message__sender__icontains=query)
        rows = rows.filter(criteria)
    if status:
        rows = rows.filter(status=status)
    if assignee == "me":
        rows = rows.filter(assignee_ref_id=request.user.pk)
    elif assignee == "unassigned":
        rows = rows.filter(assignee_ref__isnull=True)
    return render(request, "records/incidents.html", {
        "page": Paginator(rows, 50).get_page(request.GET.get("page")), "statuses": STATUSES,
        "query": query, "selected_status": status, "selected_assignee": assignee,
        "pagination_query": pagination_query(request.GET),
    })


@require_http_methods(["GET", "POST"])
def incident_detail(request, incident_id):
    error = access(request, write=request.method == "POST")
    if error is not None:
        return error
    row = get_object_or_404(Incident.objects.select_related("message", "assignee_ref"), pk=incident_id)
    form = InvestigationForm(
        request.POST if request.method == "POST" else None,
        initial={"status": row.status, "assignee": row.assignee_ref_id},
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_investigation(request.user, row.pk, **form.cleaned_data)
        except PermissionError:
            return HttpResponseForbidden("Недостаточно прав")
        except (ValueError, User.DoesNotExist) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("incident-detail", incident_id=row.pk)
    return render(request, "records/incident.html", {
        "incident": row, "form": form,
        "comments": Comment.objects.filter(incident=row).select_related("account").order_by("created_at"),
        "history": Audit.objects.filter(target=row.pk).order_by("-created_at")[:100],
    }, status=400 if form.is_bound else 200)


@require_http_methods(["GET", "POST"])
def message_detail(request, message_id):
    error = access(request, write=request.method == "POST")
    if error is not None:
        return error
    row = get_object_or_404(Message.objects.select_related("content"), pk=message_id)
    error_text = None
    if request.method == "POST":
        try:
            with transaction.atomic():
                request_evaluation(row.pk, "workspace:" + uuid4().hex)
                Audit.objects.create(actor=request.user.pk, action="policy_reevaluate", target=row.pk)
        except EvidenceUnavailable as exc:
            error_text = str(exc)
        else:
            return redirect("message-detail", message_id=row.pk)
    Audit.objects.create(actor=request.user.pk, action="view_message", target=row.pk)
    return render(request, "records/message.html", {
        "message": row, "events": MailEvent.objects.filter(message=row).order_by("created_at"),
        "error": error_text,
        "attachments": Attachment.objects.filter(message=row).order_by("created_at", "pk") if request.user.has_perm("identity.view_originals") else [],
    }, status=409 if error_text else 200)


@require_GET
def original_message(request, message_id):
    error = access(request, originals=True)
    if error is not None:
        return error
    from io import BytesIO

    row = get_object_or_404(Message.objects.select_related("original_sha_ref"), pk=message_id)
    Audit.objects.create(actor=request.user.pk, action="download_original", target=row.pk)
    response = FileResponse(
        BytesIO(bytes(row.original_sha_ref.data)), as_attachment=True,
        filename=f"message-{row.pk}.{row.format}", content_type="application/octet-stream",
    )
    response["Cache-Control"] = "no-store"
    return response