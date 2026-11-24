"""Passive attachment viewer with bounded remote rasterization."""

import base64
import json
import re
from io import BytesIO
from pathlib import PurePosixPath

import httpx
from django import forms
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pipeline.parser_client import call
from records.models import Attachment, Audit
from records.workspace import access

OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
PREVIEW_LIMIT = 20 * 1024**2


class PreviewForm(forms.Form):
    page = forms.IntegerField(min_value=1, max_value=1000, initial=1)
    scale = forms.FloatField(min_value=0.5, max_value=2, initial=1)
    highlight = forms.BooleanField(required=False)


def findings_for(row):
    content = row.message.content
    findings = content.analysis.get("findings", []) if content else []
    return [finding for finding in findings if
            finding.get("attachment") == row.name or finding.get("filename") == row.name
            or (finding.get("excerpt") and finding["excerpt"] in row.text)]


def convert_office(data, suffix):
    if not settings.MICE_CONVERTER_URL:
        raise ValueError("Office converter is not configured")
    with httpx.Client(timeout=75, trust_env=False, follow_redirects=False) as client:
        with client.stream("POST", settings.MICE_CONVERTER_URL.rstrip("/") + "/convert",
                           params={"ext": suffix[1:]}, content=data) as response:
            response.raise_for_status()
            converted = bytearray()
            for chunk in response.iter_bytes():
                if len(converted) + len(chunk) > PREVIEW_LIMIT:
                    raise ValueError("Converted document too large")
                converted.extend(chunk)
    if not converted.startswith(b"%PDF-"):
        raise ValueError("Converter did not return PDF")
    return bytes(converted)


def rasterize(row, options):
    if row.blob_sha_ref.size > PREVIEW_LIMIT:
        raise ValueError("Preview size limit")
    data = bytes(row.blob_sha_ref.data)
    if len(data) > PREVIEW_LIMIT:
        raise ValueError("Preview size limit")
    suffix = PurePosixPath(row.name).suffix.lower()
    if suffix in OFFICE:
        data = convert_office(data, suffix)
    highlights = [finding.get("excerpt", "")[:100] for finding in findings_for(row)][:5] if options["highlight"] else []
    result = call("preview", data, json.dumps({
        "page": options["page"], "scale": options["scale"], "highlights": highlights,
    }, ensure_ascii=False))
    image = base64.b64decode(result["image"], validate=True)
    pages = result["pages"]
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > PREVIEW_LIMIT or type(pages) is not int or not 1 <= pages <= 100000:
        raise ValueError("Invalid rasterized response")
    return image, pages


@require_GET
def attachment(request, attachment_id, action=None):
    error = access(request, originals=True)
    if error is not None:
        return error
    row = get_object_or_404(Attachment.objects.select_related("blob_sha_ref", "message__content"), pk=attachment_id)
    if action == "download":
        Audit.objects.create(actor=request.user.pk, action="attachment_download", target=row.pk)
        response = FileResponse(BytesIO(bytes(row.blob_sha_ref.data)), as_attachment=True,
                                filename=PurePosixPath(row.name.replace("\\", "/")).name,
                                content_type="application/octet-stream")
    elif action == "page":
        form = PreviewForm({"page": request.GET.get("page", "1"), "scale": request.GET.get("scale", "1"),
                            "highlight": request.GET.get("highlight", "")})
        if not form.is_valid():
            return HttpResponse("Некорректные параметры страницы", status=400)
        try:
            image, pages = rasterize(row, form.cleaned_data)
        except (ValueError, KeyError, TypeError, RuntimeError, httpx.HTTPError):
            return HttpResponse("Безопасный просмотр недоступен; используйте сохранённый текст", status=422)
        Audit.objects.create(actor=request.user.pk, action="attachment_preview_page", target=row.pk,
                             details={"page": form.cleaned_data["page"]})
        response = HttpResponse(image, content_type="image/png")
        response["X-Document-Pages"] = str(pages)
    else:
        Audit.objects.create(actor=request.user.pk, action="attachment_preview", target=row.pk)
        response = render(request, "records/attachment.html", {
            "attachment": row, "findings": findings_for(row),
            "text_preview": bool(re.search(r"\.(txt|csv|json|xml|eml|msg|html?|svg)$", row.name, re.I)
                                 or re.match(r"^(text/|application/(json|xml)|image/svg)", row.mime, re.I)),
        })
    response["Cache-Control"] = "no-store"
    response["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    return response