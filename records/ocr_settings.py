"""Live OCR configuration and administrator-only, expiring manual sessions."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
from django import forms
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from pipeline.parser_client import call
from records.models import Audit, Setting
from records.operations import admin_access

PROVIDERS = (("rapidocr", "RapidOCR"), ("paddleocr", "PaddleOCR"), ("surya", "Surya (экспериментальный)"))
TTL = 900
MAX_BYTES = 10 * 1024**2


def configuration():
    row = Setting.objects.filter(pk="ocr").first()
    values = {"enabled": settings.MICE_OCR_ENABLED, "provider": "rapidocr"} | (row.value if row else {})
    if values["provider"] not in dict(PROVIDERS) or not isinstance(values["enabled"], bool):
        raise ValueError("Invalid OCR configuration")
    return values


class OCRForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="OCR включён")
    provider = forms.ChoiceField(choices=PROVIDERS, label="Активный провайдер")


class TestForm(forms.Form):
    provider = forms.ChoiceField(choices=PROVIDERS, label="Провайдер для теста")
    document = forms.FileField(required=False, label="Документ (до 10 МиБ)")
    token = forms.CharField(required=False, widget=forms.HiddenInput)
    force_ocr = forms.BooleanField(required=False, initial=True, label="Принудительный OCR PDF")


def availability(provider):
    url = settings.MICE_SURYA_URL if provider == "surya" else settings.MICE_OCR_PARSER_URL
    try:
        response = httpx.get(url.rstrip("/") + "/health?provider=" + provider, timeout=4, trust_env=False)
        response.raise_for_status()
        return {"provider": provider, "available": True, **response.json()}
    except (httpx.HTTPError, ValueError):
        return {"provider": provider, "available": False}


def purge():
    from records.models import OCRTestDocument
    OCRTestDocument.objects.filter(expires_at__lte=timezone.now()).delete()


def document_for(request, token):
    from records.models import OCRTestDocument
    identifier = signing.loads(token, salt="ocr-test", max_age=TTL)
    return OCRTestDocument.objects.get(pk=identifier, owner=str(request.user.pk), expires_at__gt=timezone.now())


@require_http_methods(["GET", "POST"])
def page(request):
    denied = admin_access(request)
    if denied is not None:
        return denied
    purge()
    action = request.POST.get("action", "")
    form = OCRForm(request.POST if action == "save" else None, initial=configuration())
    test = TestForm(request.POST if action == "test" else None, request.FILES or None,
                    auto_id="test_%s", initial={"provider": configuration()["provider"], "token": request.GET.get("token", "")})
    context = {"form": form, "test_form": test}
    if action == "save" and form.is_valid():
        with transaction.atomic():
            Setting.objects.update_or_create(pk="ocr", defaults={"value": form.cleaned_data})
            Audit.objects.create(actor=request.user.pk, action="ocr_configuration", target="ocr", details=form.cleaned_data)
        context["notice"] = "Настройки сохранены. Выполняющиеся задачи сохраняют выбранный провайдер."
    if action == "test" and test.is_valid():
        try:
            from datetime import timedelta
            from records.models import OCRTestDocument
            upload = test.cleaned_data["document"]
            token = test.cleaned_data["token"]
            if upload:
                if OCRTestDocument.objects.filter(owner=str(request.user.pk)).count() >= 3:
                    raise ValueError("Temporary document limit")
                if upload.size > MAX_BYTES:
                    raise ValueError("size")
                data = upload.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("size")
                # Isolated rasterization validates the format before storage.
                call("preview", data, json.dumps({"page": 1}))
                suffix = ".pdf" if data.startswith(b"%PDF-") else ".png"
                document = OCRTestDocument.objects.create(owner=str(request.user.pk), data=data, name="document" + suffix,
                                                         expires_at=timezone.now() + timedelta(seconds=TTL))
                token = signing.dumps(str(document.pk), salt="ocr-test")
            else:
                document = document_for(request, token)
            context["token"] = token
            result = call("extract", bytes(document.data), document.name, ocr=True,
                          provider=test.cleaned_data["provider"], force_ocr=test.cleaned_data["force_ocr"])
            pages = result.get("details", {}).get("ocr", [])
            scores = [b["confidence"] for p in pages for b in p.get("blocks", []) if b.get("confidence") is not None]
            context.update(result=result, seconds=sum(p.get("seconds", 0) for p in pages),
                           pages=result.get("details", {}).get("pages", 0),
                           confidence=round(sum(scores) / len(scores), 3) if scores else None)
            if result.get("status") == "FAILED":
                context["error"] = "Распознавание завершилось ошибкой. Другой провайдер не использовался."
            test.data = test.data.copy()
            test.data["token"] = token
        except Exception:
            context["error"] = "Не удалось обработать документ: проверьте формат, размер и доступность выбранного OCR. Автозамена отключена."
    with ThreadPoolExecutor(max_workers=3) as pool:
        context["providers"] = list(pool.map(availability, dict(PROVIDERS)))
    response = render(request, "records/ocr.html", context)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET"])
def preview(request):
    denied = admin_access(request)
    if denied is not None:
        return denied
    try:
        document = document_for(request, request.GET.get("token", ""))
        result = call("preview", bytes(document.data), json.dumps({"page": int(request.GET.get("page", 1))}))
        response = HttpResponse(base64.b64decode(result["image"]), content_type="image/png")
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    except Exception:
        return HttpResponse(status=404)