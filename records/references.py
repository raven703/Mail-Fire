"""Native reference catalog. Sample personal fields never become template data."""

import hashlib

import httpx
from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from app.document_templates import TEMPLATES, match_document, template_config
from app.fingerprints import fingerprint
from pipeline.parser_client import call
from records.models import Audit, Blob, Reference
from records.workspace import access


class ReferenceForm(forms.Form):
    file = forms.FileField(label="Документ")
    template_type = forms.ChoiceField(required=False, label="Тип эталона", choices=[
        ("", "Содержимое документа"), *[(key, value["label"]) for key, value in TEMPLATES.items()],
    ])

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not 0 < value.size <= settings.MICE_MAX_MESSAGE_BYTES:
            raise forms.ValidationError("Неверный размер документа")
        return value


def prepare_reference(data, name, kind, extracted):
    if not isinstance(extracted.get("text"), str) or not extracted["text"].strip() or extracted.get("status") not in {"ANALYZED", "PARTIAL"}:
        raise ValueError("Текст не извлечён; документ не проиндексирован")
    text = extracted["text"]
    if kind:
        spec = template_config(kind)
        if not match_document(text, spec):
            raise ValueError("Образец не подтверждает тип документа")
        return {
            "name": TEMPLATES[kind]["label"] + " — шаблон",
            "data": ("document-template:" + kind).encode(),
            "text": " ".join(spec["anchors"]), "fingerprint": {"document_template": spec},
        }
    return {"name": name[:1024], "data": data, "text": text, "fingerprint": fingerprint(text)}


@transaction.atomic
def save_reference(actor, prepared):
    data = prepared["data"]
    digest = hashlib.sha256(data).hexdigest()
    Blob.objects.get_or_create(sha=digest, defaults={"data": data, "size": len(data)})
    row = Reference.objects.create(
        name=prepared["name"], blob_sha_ref_id=digest, text=prepared["text"], fingerprint=prepared["fingerprint"],
    )
    Audit.objects.create(actor=actor.pk, action="reference_upload", target=row.pk,
                         details={"template": "document_template" in row.fingerprint})
    return row


@require_http_methods(["GET", "POST"])
def references(request):
    error = access(request, originals=True)
    if error is not None:
        return error
    if request.method == "POST":
        error = access(request, write=True)
        if error is not None:
            return error
    form = ReferenceForm(request.POST if request.method == "POST" else None,
                         request.FILES if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        data = upload.read(settings.MICE_MAX_MESSAGE_BYTES + 1)
        try:
            if not 0 < len(data) <= settings.MICE_MAX_MESSAGE_BYTES:
                raise ValueError("Неверный размер документа")
            # OCR-enabled sandbox endpoint for scanned samples; never parse locally.
            extracted = call("extract", data, upload.name, ocr=True)
            prepared = prepare_reference(data, upload.name, form.cleaned_data["template_type"], extracted)
        except (ValueError, KeyError, TypeError, RuntimeError, httpx.HTTPError):
            form.add_error(None, "Документ не принят: проверьте текст, тип образца и доступность Parser/OCR.")
        else:
            save_reference(request.user, prepared)
            return redirect("references-page")
    return render(request, "records/references.html", {
        "form": form, "page": Paginator(Reference.objects.order_by("-created_at", "-pk"), 50).get_page(request.GET.get("page")),
    }, status=400 if form.is_bound else 200)