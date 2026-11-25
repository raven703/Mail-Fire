"""Analyst-requested full reanalysis, serialized against the existing pipeline."""
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_POST

from pipeline.models import WorkItem
from pipeline.services import enqueue
from records.models import Audit, Message
from records.workspace import access


@transaction.atomic
def request_reanalysis(actor, message_id, token):
    message = Message.objects.select_for_update().get(pk=message_id)
    key = "reanalyze:" + token + ":" + message.pk
    existing = WorkItem.objects.filter(deduplication_key=key).first()
    if existing:
        return existing
    if WorkItem.objects.filter(payload__message_id=message.pk, status__in=["PENDING", "RUNNING"]).exists():
        raise ValueError("Письмо уже обрабатывается")
    kind = "analysis.analyze" if getattr(settings, "MICE_UNIFIED_ANALYSIS_ENABLED", False) else "ingestion.parse"
    job = enqueue(kind, {"message_id": message.pk, "reanalysis": True}, key)
    message.status, message.error = "PENDING", None
    message.save(update_fields=["status", "error"])
    Audit.objects.create(actor=actor.pk, action="reanalyze", target=message.pk, details={"job_id": str(job.pk)})
    return job


@require_POST
def bulk_reanalyze(request):
    error = access(request, write=True)
    if error is not None:
        return error
    identifiers = list(dict.fromkeys(request.POST.getlist("message_ids")))
    if not 1 <= len(identifiers) <= 50 or any(len(value) > 36 for value in identifiers):
        return HttpResponseBadRequest("Выберите от 1 до 50 писем")
    token = request.POST.get("request_token", "")
    if len(token) != 32 or any(char not in "0123456789abcdef" for char in token):
        return HttpResponseBadRequest("Некорректный токен запроса")
    results = []
    for identifier in identifiers:
        try:
            job = request_reanalysis(request.user, identifier, token)
        except Message.DoesNotExist:
            results.append({"id": identifier, "error": "Письмо не найдено"})
        except ValueError as exc:
            results.append({"id": identifier, "error": str(exc)})
        else:
            results.append({"id": identifier, "job": job})
    return render(request, "records/reanalysis.html", {"results": results, "request_token": uuid4().hex})