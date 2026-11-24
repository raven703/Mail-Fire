"""Native HTML upload: durable acceptance only, no parsing in the web process."""

from pathlib import PurePosixPath
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pipeline.bundles import accept_bundle
from pipeline.forms import MessageUploadForm
from pipeline.ingestion import accept
from records.models import Audit


def accept_file(actor, upload, source_key):
    data = upload.read(settings.MICE_MAX_MESSAGE_BYTES + 1)
    if not 0 < len(data) <= settings.MICE_MAX_MESSAGE_BYTES:
        raise ValueError("Upload size")
    with transaction.atomic():
        if PurePosixPath(upload.name).suffix.lower() == ".zip":
            job = accept_bundle(data, source_key, upload.name)
            Audit.objects.create(actor=actor.pk, action="bundle_upload", target=str(job.pk))
            return {"bundle_job": job}
        record = accept(data, "upload", source_key, upload.name)
        Audit.objects.create(actor=actor.pk, action="message_upload", target=record.message_id)
        return {"record": record}


@require_http_methods(["GET", "POST"])
def upload_message(request):
    if not request.user.is_authenticated:
        return redirect("login-page")
    if not request.user.has_perm("identity.investigate"):
        return HttpResponseForbidden("Недостаточно прав")
    form = MessageUploadForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        initial={"delivery_id": uuid4()},
    )
    if request.method == "POST" and form.is_valid():
        uploads = form.cleaned_data["message"]
        results = []
        for index, (upload, error) in enumerate(uploads):
            result = {"name": upload.name}
            if not error:
                source_key = form.source_key(request.user.pk, index if len(uploads) > 1 else None)
                try:
                    result.update(accept_file(request.user, upload, source_key))
                except ValueError:
                    error = "Файл не принят. Проверьте размер и идентификатор доставки."
            results.append({**result, "error": error})
        failures = sum(bool(result["error"]) for result in results)
        return render(request, "pipeline/upload.html", {"results": results, "failures": failures},
                      status=400 if failures == len(results) else 202)
    return render(request, "pipeline/upload.html", {"form": form}, status=400 if form.is_bound else 200)
