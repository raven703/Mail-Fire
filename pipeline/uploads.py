"""Native HTML upload: durable acceptance only, no parsing in the web process."""

from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pipeline.forms import MessageUploadForm
from pipeline.ingestion import accept
from records.models import Audit


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
        upload = form.cleaned_data["message"]
        # Do not trust the uploaded-file size metadata alone.
        data = upload.read(settings.MICE_MAX_MESSAGE_BYTES + 1)
        try:
            with transaction.atomic():
                record = accept(data, "upload", form.source_key(request.user.pk), upload.name)
                Audit.objects.create(actor=request.user.pk, action="message_upload", target=record.message_id)
        except ValueError:
            form.add_error(None, "Письмо не принято: неверный размер или конфликт идентификатора доставки.")
        else:
            return render(request, "pipeline/upload.html", {"record": record}, status=202)
    return render(request, "pipeline/upload.html", {"form": form}, status=400 if form.is_bound else 200)