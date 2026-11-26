"""Native analyst workspace and transactional investigation actions."""

from uuid import uuid4

from django import forms
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from identity.models import User
from policy_engine.service import EvidenceUnavailable, request_evaluation
from records.models import Attachment, Audit, Category, Comment, Incident, MailEvent, Message, Policy
from records.ui_filters import filter_dates, list_period, pagination_query, resolve_period

OPEN_STATUSES = ("NEW", "ASSIGNED", "REVIEW", "REOPENED")
HIGH_RISK = 70
MEDIUM_RISK = 40
STATUS_LABELS = {
    "NEW": "Новый", "ASSIGNED": "Назначен", "REVIEW": "На проверке", "CONFIRMED": "Подтверждён",
    "FALSE_POSITIVE": "Ложное срабатывание", "CLOSED": "Закрыт", "REOPENED": "Переоткрыт",
}
STATUSES = tuple(STATUS_LABELS)
KEEP_ASSIGNEE = object()


def severity(risk):
    return "HIGH" if risk >= HIGH_RISK else "MEDIUM" if risk >= MEDIUM_RISK else "LOW"


def categories_found(incident):
    return list(dict.fromkeys(finding["category"] for finding in incident.findings or [] if finding.get("category")))


def policy_label(incident):
    names = [hit["name"] for hit in incident.policy_hits or [] if hit.get("active") and hit.get("name")]
    return ", ".join(dict.fromkeys(names)) or (incident.policy.name if incident.policy else "Исторические политики")


class InvestigationForm(forms.Form):
    status = forms.ChoiceField(choices=STATUS_LABELS.items(), label="Статус расследования")
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
def update_investigation(actor, incident_id, *, status=None, assignee=KEEP_ASSIGNEE, comment=""):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    if not actor.has_perm("identity.investigate"):
        raise PermissionError("Недостаточно прав")
    if (status is not None and status not in STATUSES) or len(comment) > 10000:
        raise ValueError("Некорректное решение")
    row = Incident.objects.select_for_update().get(pk=incident_id)
    if assignee is not KEEP_ASSIGNEE and assignee is not None:
        target = User.objects.select_for_update().get(pk=assignee.pk)
        if not target.is_active or target.role not in {"admin", "analyst"}:
            raise ValueError("Выберите действующего аналитика")
    before = {"status": row.status, "assignee": row.assignee_ref_id}
    if status is not None:
        row.status = status
    if assignee is not KEEP_ASSIGNEE:
        row.assignee_ref_id = assignee.pk if assignee else None
    row.save(update_fields=["status", "assignee_ref"])
    if comment.strip():
        Comment.objects.create(incident=row, account_id=actor.pk, text=comment.strip())
    Audit.objects.create(
        actor=actor.pk, action="incident_decision", target=row.pk,
        details={"before": before, "status": row.status, "assignee": row.assignee_ref_id},
    )
    return row


@require_GET
def incidents(request):
    error = access(request)
    if error is not None:
        return error
    resolve_period(request)
    rows = filter_dates(Incident.objects.select_related("message", "assignee_ref", "policy", "event").defer(
        "message__headers", "message__error", "event__envelope", "findings",
    ), list_period(request.GET))
    query, status, assignee = (request.GET.get(key, "").strip()[:500] for key in ("q", "status", "assignee"))
    bands = {"high": Q(risk__gte=HIGH_RISK), "medium": Q(risk__gte=MEDIUM_RISK, risk__lt=HIGH_RISK),
             "low": Q(risk__lt=MEDIUM_RISK)}
    if request.GET.get("severity") in bands:
        rows = rows.filter(bands[request.GET["severity"]])
    selected_categories = request.GET.getlist("category")[:100]
    if selected_categories:
        criteria = Q()
        for category in selected_categories:
            criteria |= Q(findings__contains=[{"category": category}])
        rows = rows.filter(criteria)
    policy = request.GET.get("policy", "").strip()[:200]
    if policy:
        matches = Incident.objects.extra(where=[
            "EXISTS (SELECT 1 FROM jsonb_array_elements(incidents.policy_hits) AS hit WHERE hit->>'name' ILIKE %s)",
        ], params=["%" + policy.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"])
        rows = rows.filter(pk__in=matches.values("pk"))
    if query:
        criteria = Q(pk=query) | Q(message_id=query) | Q(policy__name__icontains=query)
        number = query.upper().removeprefix("INC-")
        if number.isascii() and number.isdecimal() and len(number) <= 19 and 0 < int(number) <= 2**63 - 1:
            criteria |= Q(number=int(number))
        if request.user.has_perm("identity.view_originals"):
            criteria |= Q(message__subject__icontains=query) | Q(message__sender__icontains=query)
        rows = rows.filter(criteria)
    if status == "open" or "status" not in request.GET:
        rows = rows.filter(status__in=OPEN_STATUSES)
    elif status:
        rows = rows.filter(status=status)
    events = MailEvent.objects.all()
    for key in ("direction", "source"):
        if request.GET.get(key):
            events = events.filter(**{key: request.GET[key]})
    if request.GET.get("direction") or request.GET.get("source"):
        rows = rows.filter(message_id__in=events.values("message_id"))
    if request.user.has_perm("identity.view_originals"):
        if request.GET.get("sender"):
            rows = rows.filter(message__sender__icontains=request.GET["sender"])
        if request.GET.get("recipient"):
            rows = rows.alias(recipient_search=Cast("message__recipients", CharField())).filter(
                recipient_search__icontains=request.GET["recipient"][:200],
            )
    if assignee == "me":
        rows = rows.filter(assignee_ref_id=request.user.pk)
    elif assignee == "unassigned":
        rows = rows.filter(assignee_ref__isnull=True)
    elif assignee:
        rows = rows.filter(assignee_ref__username__icontains=assignee)
    sort = {"date": "created_at", "risk": "risk"}.get(request.GET.get("sort"), "created_at")
    if request.GET.get("sort") == "sender" and request.user.has_perm("identity.view_originals"):
        sort = "message__sender"
    rows = rows.order_by(("" if request.GET.get("order") == "asc" else "-") + sort, "pk")
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    for row in page:
        row.severity = severity(row.risk)
        row.policy_label = policy_label(row)
        row.status_label = STATUS_LABELS.get(row.status, row.status)
        row.sender_name = row.message.sender.split("@", 1)[0]
    return render(request, "records/incidents.html", {
        "page": page, "statuses": STATUS_LABELS.items(), "query": query,
        "selected_status": status, "selected_assignee": assignee, "pagination_query": pagination_query(request.GET),
        "categories": Category.objects.filter(active=True).exclude(mode="label").exclude(
            pk__in=[key for key in ("RU_INN", "RU_PHONE") if key not in selected_categories]
        ).order_by("name"), "selected_categories": selected_categories,
        "policy_options": Policy.objects.order_by("name").values_list("name", flat=True).distinct(),
        "sources": MailEvent.objects.values_list("source", flat=True).distinct().order_by("source"),
    })



@require_http_methods(["GET", "POST"])
def incident_detail(request, incident_id):
    error = access(request, write=request.method == "POST")
    if error is not None:
        return error
    row = get_object_or_404(Incident.objects.select_related("message", "assignee_ref", "policy", "event"), pk=incident_id)
    from records.category_picker import LabelForm
    from records.incident_training import save_incident_example

    training_action = request.method == "POST" and request.POST.get("action") == "training_example"
    training_form = None
    can_train = request.user.has_perm("identity.investigate") and request.user.has_perm("identity.view_originals")
    if can_train and (training_action or request.GET.get("training") == "1"):
        training_form = LabelForm(request.POST if training_action else None,
                                            initial={"labels": ["NORMAL"] if row.status == "FALSE_POSITIVE" else categories_found(row)[:20]})
    editing = request.POST.get("action") if request.method == "POST" else request.GET.get("edit")
    form = None
    can_edit = request.user.has_perm("identity.investigate")
    if can_edit and editing in {"assignee", "decision"}:
        form = InvestigationForm(
            request.POST if request.method == "POST" else None,
            initial={"status": row.status, "assignee": row.assignee_ref_id},
        )
        for field in (("status", "comment") if editing == "assignee" else ("assignee",)):
            form.fields.pop(field)
    if training_action:
        if training_form is None:
            return HttpResponseForbidden("Нет доступа к содержимому письма")
        if training_form.is_valid():
            try:
                save_incident_example(request.user, row.pk, **training_form.cleaned_data)
            except (ValueError, PermissionError) as exc:
                training_form.add_error(None, str(exc))
            else:
                return redirect("incident-detail", incident_id=row.pk)
    elif request.method == "POST" and form is not None and form.is_valid():
        try:
            update_investigation(request.user, row.pk, **form.cleaned_data)
        except PermissionError:
            return HttpResponseForbidden("Недостаточно прав")
        except (ValueError, User.DoesNotExist) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("incident-detail", incident_id=row.pk)
    return render(request, "records/incident.html", {
        "incident": row, "form": form, "editing": editing, "can_edit": can_edit,
        "severity": severity(row.risk), "policy_label": policy_label(row),
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "training_form": training_form, "can_train": can_train,
        "comments": Comment.objects.filter(incident=row).select_related("account").order_by("created_at"),
        "history": Audit.objects.filter(target=row.pk).order_by("-created_at")[:100],
    }, status=400 if request.method == "POST" else 200)


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
    from records.processing_status import attachment_reason, describe, latest_jobs
    processing = describe(row, latest_jobs([row]).get(row.pk))
    attachments = list(Attachment.objects.filter(message=row).select_related("blob_sha_ref").only(
        "id", "name", "mime", "status", "details", "blob_sha_ref__size",
    ).order_by("created_at", "pk")) if request.user.has_perm("identity.view_originals") else []
    for attachment in attachments:
        attachment.processing_reason = attachment_reason(attachment)
    return render(request, "records/message.html", {
        "processing": processing,
        "message": row, "events": MailEvent.objects.filter(message=row).order_by("created_at"),
        "history": Audit.objects.filter(target=row.pk).order_by("-created_at")[:100],
        "incidents": Incident.objects.filter(message=row).select_related("policy").only(
            "id", "number", "risk", "status", "policy__name",
        ).order_by("-created_at"),
        "error": error_text,
        "reanalysis_token": uuid4().hex,
        "attachments": attachments,
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