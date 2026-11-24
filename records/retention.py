"""Bounded native retention with locked legal-hold checks and durable worker jobs."""

from datetime import timedelta

from django import forms
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from pipeline.models import WorkItem
from pipeline.services import enqueue, finish, locked_current
from policy_engine.models import AnalysisRevision, Evaluation
from records.models import (
    Attachment,
    Audit,
    Comment,
    ImportRecord,
    Incident,
    MailEvent,
    Message,
    Outbox,
    SemanticChunk,
    Setting,
    TrainingExample,
)
from records.operations import admin_access

DEFAULTS = {"ordinary_days": 30, "unconfirmed_days": 365, "confirmed_days": 365, "paused": True}


class RetentionForm(forms.Form):
    ordinary_days = forms.IntegerField(min_value=1, max_value=36500, label="Обычные письма, дней")
    unconfirmed_days = forms.IntegerField(min_value=1, max_value=36500, label="Неподтверждённые инциденты, дней")
    confirmed_days = forms.IntegerField(min_value=1, max_value=36500, label="Подтверждённые инциденты, дней")
    paused = forms.BooleanField(required=False, label="Очистка приостановлена")


def config():
    row = Setting.objects.filter(pk="retention").first()
    values = DEFAULTS | (row.value if row else {})
    form = RetentionForm(values)
    if not form.is_valid():
        raise ValueError("Invalid retention configuration")
    return form.cleaned_data


def expired(created_at, statuses, values, now):
    days = values["confirmed_days"] if "CONFIRMED" in statuses else values["unconfirmed_days"] if statuses else values["ordinary_days"]
    return created_at <= now - timedelta(days=days)


def message_jobs(message, events, revisions):
    return WorkItem.objects.filter(
        Q(payload__message_id=message.pk) | Q(payload__event_id__in=events)
        | Q(payload__analysis_id__in=[str(value) for value in revisions])
    )


def cleanup(job):
    values = config()
    deleted, candidates, skipped = [], [], 0
    if not values["paused"]:
        now = timezone.now()
        cutoff = now - timedelta(days=min(values[key] for key in ("ordinary_days", "unconfirmed_days", "confirmed_days")))
        ids = list(Message.objects.filter(legal_hold=False, created_at__lte=cutoff).order_by("created_at").values_list("pk", flat=True)[:500])
        for identifier in ids:
            with transaction.atomic():
                locked_current(job.pk, job.token)
                message = Message.objects.select_for_update().filter(pk=identifier).first()
                if message is None or message.legal_hold:
                    skipped += 1
                    continue
                incidents = Incident.objects.filter(message=message)
                statuses = list(incidents.values_list("status", flat=True))
                if not expired(message.created_at, statuses, values, now):
                    skipped += 1
                    continue
                events = list(MailEvent.objects.filter(message=message).values_list("pk", flat=True))
                revisions = list(AnalysisRevision.objects.filter(message=message).values_list("pk", flat=True))
                jobs = message_jobs(message, events, revisions)
                # Preserve evidence while any analysis/policy/notification work is live.
                notices = Outbox.objects.filter(incident__message=message)
                if jobs.filter(status__in=["PENDING", "RUNNING"]).exists() or notices.exclude(status="SENT").exists():
                    skipped += 1
                    continue
                candidates.append(identifier)
                if job.payload.get("dry_run", True):
                    continue
                Evaluation.objects.filter(analysis_id__in=revisions).delete()
                AnalysisRevision.objects.filter(pk__in=revisions).delete()
                TrainingExample.objects.filter(source_incident__in=incidents).update(source_incident=None)
                Comment.objects.filter(incident__in=incidents).delete()
                notices.delete()
                incidents.delete()
                ImportRecord.objects.filter(message=message).delete()
                Attachment.objects.filter(message=message).delete()
                MailEvent.objects.filter(message=message).delete()
                jobs.delete()
                content_id = message.content_id
                message.delete()
                if content_id and not Message.objects.filter(content_id=content_id).exists():
                    SemanticChunk.objects.filter(source_type="content", source_id=content_id).delete()
                # Keep blobs/content until reference-aware GC also accounts for
                # durable job payloads. Never blindly delete globally unlinked blobs.
                Audit.objects.create(actor="retention", action="message_deleted", target=identifier,
                                     details={"policy": values})
                deleted.append(identifier)
                # Checkpoint each committed deletion so a retry does not lose
                # its durable count after a worker crash between messages.
                current = locked_current(job.pk, job.token)
                prior = current.output.get("deleted", [])
                current.output = {**current.output, "deleted": list(dict.fromkeys(prior + [identifier]))}
                current.save(update_fields=["output"])
    with transaction.atomic():
        current = locked_current(job.pk, job.token)
        deleted = list(dict.fromkeys(current.output.get("deleted", []) + deleted))
        finish(job.pk, job.token, {"paused": values["paused"], "candidates": candidates, "deleted": deleted, "skipped": skipped})


@require_http_methods(["GET", "POST"])
def retention(request):
    error = admin_access(request)
    if error is not None:
        return error
    values = config()
    form = RetentionForm(request.POST if request.method == "POST" and request.POST.get("action") == "save" else None, initial=values)
    message = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save" and form.is_valid():
            with transaction.atomic():
                Setting.objects.update_or_create(pk="retention", defaults={"value": form.cleaned_data})
                Audit.objects.create(actor=request.user.pk, action="retention_config", target="retention", details=form.cleaned_data)
            return redirect("retention-page")
        if action in {"preview", "cleanup", "gc-preview", "gc-delete"}:
            if action in {"cleanup", "gc-delete"} and request.POST.get("confirm") != "DELETE_EXPIRED":
                message = "Требуется подтверждение DELETE_EXPIRED"
            else:
                from uuid import uuid4

                with transaction.atomic():
                    kind = "maintenance.gc" if action.startswith("gc-") else "maintenance.retention"
                    dry_run = action not in {"cleanup", "gc-delete"}
                    job = enqueue(kind, {"dry_run": dry_run}, "retention:" + uuid4().hex)
                    Audit.objects.create(actor=request.user.pk, action="retention_request", target=str(job.pk), details={"dry_run": dry_run, "kind": kind})
                return redirect("retention-page")
    return render(request, "records/retention.html", {
        "form": form, "error": message,
        "jobs": WorkItem.objects.filter(kind__in=["maintenance.retention", "maintenance.gc"]).order_by("-created_at")[:20],
    }, status=400 if message or form.is_bound else 200)


@require_POST
def legal_hold(request, message_id):
    error = admin_access(request)
    if error is not None:
        return error
    reason = request.POST.get("reason", "").strip()
    if not 3 <= len(reason) <= 1000 or request.POST.get("enabled") not in {"true", "false"}:
        from django.http import HttpResponseBadRequest

        return HttpResponseBadRequest("Укажите причину (3–1000 символов) и состояние legal hold")
    with transaction.atomic():
        row = get_object_or_404(Message.objects.select_for_update(), pk=message_id)
        row.legal_hold = request.POST["enabled"] == "true"
        row.save(update_fields=["legal_hold"])
        Audit.objects.create(actor=request.user.pk, action="legal_hold", target=row.pk,
                             details={"enabled": row.legal_hold, "reason": reason})
    return redirect("message-detail", message_id=row.pk)